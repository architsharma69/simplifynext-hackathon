"""Local dev convenience: launches the FastAPI backend and the Telegram bot together.

Not meant to be imported — this is a plain script, invoked as
`python ui/telegram/run_dev.py`. It spawns the two as separate subprocesses
(they're independent services in production) and tears both down together on
Ctrl+C. Mirrors ui/streamlit/run_dev.py.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
BOT_PATH = Path(__file__).resolve().parent / "bot.py"

API_PORT = int(os.getenv("API_PORT", "8000"))


def main() -> int:
    api_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.main:app", "--reload", "--port", str(API_PORT)],
        cwd=SRC_DIR,
    )

    # Give the API a moment to come up before the bot's first request hits it.
    time.sleep(2)

    bot_env = {**os.environ, "BRO_API_URL": f"http://localhost:{API_PORT}"}
    bot_proc = subprocess.Popen(
        [sys.executable, str(BOT_PATH)],
        cwd=REPO_ROOT,
        env=bot_env,
    )

    procs = [api_proc, bot_proc]
    exit_code = 0
    try:
        while True:
            for proc in procs:
                ret = proc.poll()
                if ret is not None:
                    print(f"Process {proc.args} exited with code {ret}, shutting down.")
                    exit_code = ret
                    return exit_code
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")
        return 0
    finally:
        for proc in procs:
            if proc.poll() is None:
                proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    sys.exit(main())
