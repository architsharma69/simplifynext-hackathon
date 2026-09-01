# api

## `__init__.py`
Empty. Just marks this folder as a Python package.

## `entrypoint.py`
The single doorway from the API into the flow.

- `CROSS_TURN_FIELDS` — Not a function, just the list of state fields that carry over between chat turns (everything else resets on every new question).
- `run_orchestrator(user_input, session_state)` — Runs one question through the flow and returns the answer, which specialists ran, and what should be remembered for the user's next question. Keeps old routing decisions from leaking into the next turn.

## `sessions.py`
A very simple in-memory store for who's said what.

- `get_session(platform, user_id)` — Looks up a user's saved conversation state by platform and ID. Returns an empty state if they're new.
- `save_session(platform, user_id, session_state)` — Saves a user's latest conversation state so it can be picked back up on their next message.

## `main.py`
The FastAPI app itself.

- `ChatRequest` — Not a function, a schema: defines what a valid incoming chat request must contain (`platform`, `user_id`, `message`).
- `ChatResponse` — Not a function, a schema: defines what every successful chat reply looks like (`response` text plus a `metadata` dict).
- `health()` — The `/health` endpoint. Just confirms the server is up and responding.
- `chat(req)` — The `/chat` endpoint. Loads the user's session, runs their message through the orchestrator, saves the updated session, and returns the answer — or a clean error message if something breaks.