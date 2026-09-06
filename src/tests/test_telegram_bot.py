import asyncio

import httpx
import pytest

from ui.telegram import api_client, bot


class _FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class _FakeAsyncClient:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error

    def __call__(self, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def post(self, *args, **kwargs):
        if self._error is not None:
            raise self._error
        return self._response


def test_send_message_success(monkeypatch):
    fake_client = _FakeAsyncClient(
        response=_FakeResponse(
            200, {"response": "hi", "metadata": {"invoked_specialists": ["hr"]}}
        )
    )
    monkeypatch.setattr(api_client.httpx, "AsyncClient", fake_client)

    result = asyncio.run(api_client.send_message("http://api", "u1", "hello"))

    assert result["response"] == "hi"
    assert result["metadata"]["invoked_specialists"] == ["hr"]


def test_send_message_non_200_raises(monkeypatch):
    fake_client = _FakeAsyncClient(response=_FakeResponse(500, text="boom"))
    monkeypatch.setattr(api_client.httpx, "AsyncClient", fake_client)

    with pytest.raises(api_client.OrchestratorError):
        asyncio.run(api_client.send_message("http://api", "u1", "hello"))


def test_send_message_connection_error_raises(monkeypatch):
    fake_client = _FakeAsyncClient(error=httpx.ConnectError("nope"))
    monkeypatch.setattr(api_client.httpx, "AsyncClient", fake_client)

    with pytest.raises(api_client.OrchestratorError):
        asyncio.run(api_client.send_message("http://api", "u1", "hello"))


def test_format_response_with_specialists():
    text = bot.format_response("answer", ["hr", "finance"])
    assert text == "answer\n\n(Consulted: hr, finance)"


def test_format_response_without_specialists():
    assert bot.format_response("answer", []) == "answer"


class _FakeMessage:
    def __init__(self, text):
        self.text = text
        self.replies = []

    async def reply_text(self, text, **kwargs):
        self.replies.append(text)


class _FakeUser:
    def __init__(self, user_id):
        self.id = user_id


class _FakeChat:
    def __init__(self, chat_id):
        self.id = chat_id


class _FakeUpdate:
    def __init__(self, user_id, chat_id, text):
        self.effective_user = _FakeUser(user_id)
        self.effective_chat = _FakeChat(chat_id)
        self.message = _FakeMessage(text)


class _FakeBot:
    def __init__(self):
        self.typing_calls = 0

    async def send_chat_action(self, chat_id, action):
        self.typing_calls += 1


class _FakeContext:
    def __init__(self):
        self.bot = _FakeBot()


def test_handle_message_success(monkeypatch):
    calls = {}

    async def fake_send_message(base_url, user_id, message):
        calls["args"] = (base_url, user_id, message)
        return {"response": "answer", "metadata": {"invoked_specialists": ["finance"]}}

    monkeypatch.setattr(bot, "send_message", fake_send_message)

    update = _FakeUpdate(user_id=42, chat_id=99, text="what's our budget?")
    context = _FakeContext()

    asyncio.run(bot.handle_message(update, context))

    assert calls["args"] == (bot.API_BASE_URL, "42", "what's our budget?")
    assert update.message.replies == ["answer\n\n(Consulted: finance)"]


def test_handle_message_orchestrator_error(monkeypatch):
    # bot.py imports api_client via its own sys.path insert (same trick as
    # ui/streamlit/app.py), so it holds a separate module object from the
    # "ui.telegram.api_client" import above — raise the class bot.py itself
    # catches, not api_client.OrchestratorError, which is a distinct class.
    async def fake_send_message(base_url, user_id, message):
        raise bot.OrchestratorError("down")

    monkeypatch.setattr(bot, "send_message", fake_send_message)

    update = _FakeUpdate(user_id=7, chat_id=1, text="hello")
    context = _FakeContext()

    asyncio.run(bot.handle_message(update, context))

    assert update.message.replies == [bot.ERROR_TEXT]


def test_newchat_bumps_session_suffix():
    update = _FakeUpdate(user_id=123, chat_id=1, text="/newchat")
    context = _FakeContext()

    assert bot._session_user_id(123) == "123"
    asyncio.run(bot.newchat(update, context))
    assert bot._session_user_id(123) == "123:1"


def test_shutdown_replies_and_schedules_teardown(monkeypatch):
    scheduled = {}

    class _FakeLoop:
        def call_later(self, delay, func, *args):
            scheduled["delay"] = delay
            scheduled["func"] = func
            scheduled["args"] = args

    monkeypatch.setattr(bot.asyncio, "get_event_loop", lambda: _FakeLoop())

    update = _FakeUpdate(user_id=1, chat_id=1, text="/shutdown")
    context = _FakeContext()

    asyncio.run(bot.shutdown(update, context))

    assert update.message.replies == ["Shutting down the API and this bot..."]
    assert scheduled["func"] is bot._shutdown_everything
    assert scheduled["args"] == (bot.API_PORT,)
    assert scheduled["delay"] == 1.0
