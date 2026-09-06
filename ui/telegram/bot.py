import asyncio
import contextlib
import logging
import os
import signal
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

_UI_DIR = Path(__file__).resolve().parent
if str(_UI_DIR) not in sys.path:
    sys.path.insert(0, str(_UI_DIR))

from api_client import OrchestratorError, send_message

load_dotenv()

logger = logging.getLogger(__name__)

API_BASE_URL = os.getenv("BRO_API_URL", "http://localhost:8000")
API_PORT = urlparse(API_BASE_URL).port or 8000
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

WELCOME_TEXT = (
    "🧭 Business Resiliance Operator\n"
    "Ask about HR, finance, documents, or anything else your business needs."
)
ERROR_TEXT = (
    "Sorry, something went wrong reaching the orchestrator. Please try again in a moment."
)
TYPING_REFRESH_SECONDS = 4

# Per-Telegram-user session suffix, bumped by /newchat to fake a fresh
# server-side session — there's no reset endpoint, get_session() just hands
# back an empty state the first time it sees a given user_id.
_session_suffix: dict[int, int] = {}


def _session_user_id(telegram_user_id: int) -> str:
    suffix = _session_suffix.get(telegram_user_id, 0)
    return f"{telegram_user_id}:{suffix}" if suffix else str(telegram_user_id)


def format_response(response_text: str, invoked_specialists: list) -> str:
    if not invoked_specialists:
        return response_text
    return f"{response_text}\n\n(Consulted: {', '.join(invoked_specialists)})"


async def _keep_typing(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    # Telegram's typing indicator auto-expires after ~5s, so a single call
    # isn't enough to cover a multi-minute orchestrator turn.
    while True:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(TYPING_REFRESH_SECONDS)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME_TEXT)


async def newchat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_user_id = update.effective_user.id
    _session_suffix[telegram_user_id] = _session_suffix.get(telegram_user_id, 0) + 1
    await update.message.reply_text("Started a new conversation.")


def _kill_listeners_on_port(port: int) -> None:
    try:
        pids = subprocess.check_output(
            ["lsof", "-tiTCP:" + str(port), "-sTCP:LISTEN"], text=True
        ).split()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pids = []
    for pid in pids:
        try:
            os.kill(int(pid), signal.SIGKILL)
        except (ProcessLookupError, ValueError):
            pass


def _shutdown_everything(api_port: int) -> None:
    """Kill the API (by port) and this bot process itself.

    Mirrors ui/streamlit/app.py's danger-zone button. Deliberately not
    restricted to a specific Telegram user — anyone who can message this bot
    can trigger it, same trust model as the Streamlit button being visible to
    anyone with the page open. Revisit if the bot is ever exposed beyond a
    small trusted group.
    """
    _kill_listeners_on_port(api_port)
    os.kill(os.getpid(), signal.SIGTERM)


async def shutdown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Shutting down the API and this bot...")
    asyncio.get_event_loop().call_later(1.0, _shutdown_everything, API_PORT)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_id = _session_user_id(update.effective_user.id)
    message = update.message.text

    typing_task = asyncio.create_task(_keep_typing(context, chat_id))
    try:
        result = await send_message(API_BASE_URL, user_id, message)
    except OrchestratorError as exc:
        logger.warning("orchestrator call failed for user_id=%s: %s", user_id, exc)
        await update.message.reply_text(ERROR_TEXT)
        return
    finally:
        typing_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await typing_task

    response_text = result.get("response", "")
    invoked_specialists = result.get("metadata", {}).get("invoked_specialists", [])
    await update.message.reply_text(format_response(response_text, invoked_specialists))

    # metadata.chart_data / metadata.document aren't populated by the API
    # yet (Streamlit checks the same keys and always gets None today), so
    # there's nothing real to forward as a chart image or document attachment
    # until the backend starts returning them.


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not set. Add it to your .env (get one from @BotFather)."
        )

    logging.basicConfig(level=logging.INFO)

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("newchat", newchat))
    application.add_handler(CommandHandler("shutdown", shutdown))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("BRO Telegram bot starting (API_BASE_URL=%s)", API_BASE_URL)
    application.run_polling()


if __name__ == "__main__":
    main()
