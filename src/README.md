# src

- `main.py` — Currently empty. Not used yet.

See each subfolder's own README for what's inside it:
- `flows/` — the core control flow that routes and answers user questions.
- `api/` — the FastAPI web server that exposes the flow over HTTP.
- `tests/` — automated tests for everything above.

## Running the tests

The test files under `tests/` aren't meant to be run directly (`python test_api.py` does nothing useful — the test functions never get called on their own). Instead, `pytest` finds and runs them for you:

```bash
pytest src/tests -v
```

`pytest` scans `src/tests/` for files/functions matching `test_*`, imports each file, and calls every `test_*` function it finds. Each one is a plain Python function that follows the same shape:

1. **Arrange** — build a fresh piece of the app (e.g. an `OrchestratorFlow`, or the FastAPI `TestClient`).
2. **Act** — run it with a sample input, exactly like a real request would.
3. **Assert** — check the result is what's expected. If an `assert` fails, pytest reports it as a failure with the actual vs. expected values; if every `assert` in the function passes, pytest marks it green.

A couple of pytest-specific tricks show up in `test_api.py`:
- It uses FastAPI's `TestClient` to call `/health` and `/chat` in-process — no real server needs to be running.
- `test_chat_error_returns_clean_envelope` uses the `monkeypatch` fixture (pytest supplies it automatically as a function argument) to temporarily swap `run_orchestrator` for a function that raises an error, so it can test the API's error handling without actually breaking anything.

## Running the API manually

Unlike the tests, the API is meant to be run and hit like a real server when you want to manually try things out.

**1. Start the server**, from the repo root:
```bash
uvicorn api.main:app --reload --app-dir src
```
- `--app-dir src` is what lets uvicorn find the `api` package (since the app code lives under `src/`, not the repo root).
- `--reload` restarts the server automatically whenever you save a change to the code.
- By default it listens on `http://localhost:8000`.

**2. Send it requests.** A few ways:
- **Browser, easiest for poking around** — open `http://localhost:8000/docs`. This is FastAPI's built-in interactive Swagger UI (comes free with every FastAPI app). Expand `POST /chat`, click "Try it out," fill in the JSON body, hit Execute, and see the real response. (Visiting bare `http://localhost:8000/` will 404 — there's no route defined at `/`, only `/health` and `/chat`. That's expected, not an error.)
- **curl**:
  ```bash
  curl -X POST localhost:8000/chat \
    -H 'Content-Type: application/json' \
    -d '{"platform":"cli","user_id":"me","message":"How many employees are on the roster?"}'
  ```
- **Postman / Insomnia** — same idea, POST to `http://localhost:8000/chat` with a JSON body.

**3. Stop the server** with `Ctrl+C` in the terminal it's running in.

**If `Ctrl+C` doesn't work** (a known macOS quirk with `--reload`'s watcher process) or you get `[Errno 48] Address already in use` on your next start, find and kill whatever's still holding port 8000:
```bash
lsof -i :8000 -sTCP:LISTEN   # shows the PID(s) listening on the port
kill <PID>                   # add -9 if a plain kill doesn't stop it after a couple seconds
```