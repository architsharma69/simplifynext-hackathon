## 1. Create the Flow Structure (Completed)

- [x] Project skeleton set up as `src/flows/` (Flow + state) and `src/api/` (backend entrypoint) — `/crews` was added in Section 2; `/ui` folders are still pending Sections 4-5.
- [x] Shared state schema defined as `OrchestratorState` (Pydantic) in `src/flows/state.py` — `conversation_history`, `active_agent_outputs`, `pending_actions`, `business_context`, plus per-turn fields.
- [x] `OrchestratorFlow(Flow[OrchestratorState])` scaffolded in `src/flows/orchestrator_flow.py` with a `@start()` step that receives the raw user message.
- [x] Routing/intent `@listen` step added — now calls the real Orchestrator agent (Section 2) rather than a placeholder.
- [x] One `@listen` method added per specialist (HR, Finance, Document), each calling a placeholder crew function and writing results into shared state.
- [x] Branching implemented with `@router` + `and_()` so multiple specialists can run for one request, and synthesis waits until all of them are done.
- [x] Consultant `@listen` added as `run_consultant_review()` — deliberately *not* wired into the per-turn chain yet, since it's meant to run on a schedule, not every turn.
- [x] Final synthesis step added — combines all specialist outputs into one response via the real Orchestrator agent.
- [x] Flow state persistence wired up via CrewAI's built-in SQLite persistence (`@persist()`).
- [x] Minimal test harness written — `src/tests/test_orchestrator_flow.py` runs the Flow end-to-end with sample queries.
- [x] Logging added at every Flow step (which branch ran, truncated input/output) for debugging and demoing.

## 2. Create the Orchestrator Agent (Completed)

- [x] Orchestrator's role, goal, and backstory defined in `src/crews/orchestrator/config/agents.yaml` — emphasizes synthesis/delegation, never doing specialist work itself.
- [x] LLM backend configured centrally in `Config/config.py` (`ORCHESTRATOR_MODEL`, defaults to `openai/gpt-4o-mini`) so the model/provider can change without touching agent code.
- [x] Routing logic built as a standalone CrewAI `Agent.kickoff()` call (no `Task`/`Crew` needed — the Orchestrator does no multi-step work of its own) with structured JSON output: which specialist(s) to invoke and a rephrased sub-query for each.
- [x] Synthesis built the same way — combines every specialist's output into one coherent response, calling out conflicts rather than silently picking a side.
- [x] Orchestrator has visibility into `business_context`, passed into every routing call so decisions are context-aware, not single-turn.
- [x] Delegation wired directly into the Flow's `@listen` steps — the Orchestrator's `route_type` decision drives which branch (`delegate`/`direct`/`clarify`) the Flow takes.
- [x] Guardrails added via a Pydantic schema (`RoutingDecision`) that validates the LLM's structured output — every field required, so malformed output fails loudly instead of corrupting state.
- [x] Fallback path added: the LLM can pick `clarify` itself when genuinely unsure, and a `try`/`except` around the whole routing call falls back to a safe clarifying question if the LLM call fails outright.
- [x] `run_orchestrator(user_input, session_state) -> response` written in `src/api/entrypoint.py` — entrypoint ended up in `/api` rather than `/shared`, alongside the FastAPI app it serves.
- [x] Orchestrator unit-tested in isolation with sample queries (pure HR, pure Finance, mixed, ambiguous) in `src/tests/test_orchestrator_agent.py`, run live against the real model.
- [x] Bonus, beyond the original scope: the Orchestrator can also answer a question directly itself (`route_type: "direct"`) when it isn't something any specialist handles — added per a later requirement, not in the original plan.

## 3. Create the Shared Backend API (Completed)

- [x] Minimal FastAPI app scaffolded at `src/api/main.py` — the whole backend package ended up living at `/api` rather than `/shared` — exposing `POST /chat` and `GET /health`.
- [x] `/chat` calls `run_orchestrator()` from `src/api/entrypoint.py`, passing in the session state for that `(platform, user_id)` pair.
- [x] Session state storage implemented as a simple in-memory dict, keyed by `(platform, user_id)`, in `src/api/sessions.py`.
- [x] Session lookup/creation helper (`get_session`) returns a fresh empty state for a new `user_id`, and resumes existing state for returning users.
- [x] Request validation via Pydantic (`ChatRequest`/`ChatResponse`) and clean error responses — a Flow failure returns a 500 with a friendly message, not a raw stack trace.
- [x] `GET /health` added for quick sanity checks.
- [x] API run locally via `uvicorn` and verified directly with `curl` before any UI was built.
- [x] Per-request logging added — platform, user, and which specialists were invoked.

## 4. Create the Streamlit UI

- [ ] Scaffold a basic Streamlit app (`/ui/streamlit/app.py`) with `st.chat_message` / `st.chat_input` for a chat-style interface.
- [ ] Wire the chat input to call the FastAPI `/chat` endpoint (e.g. via `requests` or `httpx`), passing `platform="streamlit"` and a `streamlit_session_id` as `user_id`.
- [ ] Use `st.session_state` to hold conversation history locally for display, and generate/persist a stable `streamlit_session_id` per browser session so the API can match it to the right server-side state.
- [ ] Add a sidebar or tab structure so the user can switch between chatting with the Orchestrator vs. a specific specialist agent directly (per your earlier design intent).
- [ ] Add basic loading/spinner state while the Flow executes (agent calls can take a few seconds).
- [ ] Add a simple panel/expander showing which specialist agent(s) were invoked for the last response — good for demoing the multi-agent behavior to hackathon judges.
- [ ] Add placeholder areas for forecasts/visualizations (e.g. `st.plotly_chart` or `st.line_chart`) that Finance/HR agents can populate once their tools produce data.
- [ ] Add a way to display Document Generation agent outputs (e.g. downloadable file via `st.download_button` if it produces PDFs/docs).
- [ ] Handle errors gracefully in the UI (agent failure, timeout) with a user-friendly fallback message instead of a raw stack trace.
- [ ] Style/polish pass — title, business branding, minimal layout cleanup (low priority, do last).

## 5. Create the Telegram Bot Wrapper

- [ ] Set up a Telegram bot via BotFather, get the API token, store it in env config.
- [ ] Use `python-telegram-bot` (or `aiogram`) to scaffold the bot with a basic message handler.
- [ ] On each incoming Telegram message, call the FastAPI `/chat` endpoint with `platform="telegram"` and the Telegram user ID as `user_id` (so conversation state maps 1:1 to Telegram users, independent of any Streamlit sessions).
- [ ] Return the Orchestrator's response back to the user as a Telegram message; handle CrewAI's longer response times with a "typing..." indicator (`send_chat_action`).
- [ ] Handle non-text outputs (e.g. Document agent generating a file) by sending them as Telegram documents/attachments rather than raw text.
- [ ] Add minimal error handling (API timeout, malformed response) with a friendly fallback message to the Telegram user.
- [ ] Test end-to-end: Telegram message → FastAPI `/chat` → shared orchestrator function → Flow → specialist crews → response → back to Telegram.
- [ ] Confirm both UIs work concurrently against the same running API (open Streamlit and message the bot in parallel) to validate session isolation.
