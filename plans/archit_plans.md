## 1. Create the Flow Structure

- [ ] Set up project skeleton: `/flows`, `/crews/hr`, `/crews/document`, `/crews/finance`, `/crews/consultant`, `/shared` (backend entrypoint), `/ui/streamlit`, `/ui/telegram`.
- [ ] Define the shared state schema (Pydantic `BaseModel`) the Flow will carry — e.g. `conversation_history`, `active_agent_outputs`, `pending_actions`, `business_context`.
- [ ] Scaffold the top-level `OrchestratorFlow(Flow[StateSchema])` class with a `@start()` method that receives the raw user message.
- [ ] Add a routing/intent step (`@listen`) that classifies the user's request — which specialist crew(s) need to be invoked (can be a lightweight LLM call or the Orchestrator agent itself, see Section 2).
- [ ] Add one `@listen` method per specialist crew (HR, Document, Finance) that kicks off that crew's `.kickoff()` with the relevant slice of state, and writes results back into shared state.
- [ ] Add conditional/branching logic using `or_`/`and_`/router patterns for cases where multiple specialist crews need to run (sequentially or in parallel) for a single user request.
- [ ] Add a `@listen` step for the Consultant crew that runs asynchronously/on a schedule (not on every user turn) — monitors tool usage/outputs from other crews and proposes improvements.
- [ ] Add a final synthesis step where the Orchestrator agent consolidates all specialist outputs into one coherent response for the user.
- [ ] Wire up persistence for Flow state (CrewAI's built-in SQLite state persistence, or a custom store) so conversations can resume across sessions.
- [ ] Write a minimal test harness that runs the Flow end-to-end with a mocked user query and dummy crew responses, to validate the control flow before agents are fully built.
- [ ] Add logging/tracing at each Flow step (which crew was invoked, inputs/outputs) for debugging and for demoing the "agents collaborating" story.

## 2. Create the Orchestrator Agent

- [ ] Define the Orchestrator's role, goal, and backstory (CrewAI `Agent` config) — emphasize its job is synthesis and delegation, not doing domain work itself.
- [ ] Decide and configure the LLM backend via LiteLLM (`litellm.completion` model string) in a central config file so the provider can be swapped later without touching agent code.
- [ ] Build the intent-classification/routing logic as an explicit Orchestrator **Task** — output should be structured (e.g. JSON: which specialist(s) to invoke, what sub-query to send each).
- [ ] Define the "synthesis" Task — takes outputs from all invoked specialist crews and produces a single user-facing response, resolving conflicts (e.g. HR vs Finance recommendations) if they arise.
- [ ] Give the Orchestrator agent visibility into `business_context` (from shared state) so its routing/synthesis decisions are context-aware, not just single-turn.
- [ ] Implement the actual delegation mechanism connecting Orchestrator decisions to the Flow's `@listen` steps (i.e. Orchestrator output determines which Flow branch executes).
- [ ] Add guardrails/validation on the Orchestrator's structured output (e.g. Pydantic schema for routing decisions) so malformed LLM output doesn't break the Flow.
- [ ] Add a fallback path for when the Orchestrator can't confidently route a request (e.g. ask a clarifying question back to the user instead of guessing).
- [ ] Write a `run_orchestrator(user_input, session_state) -> response` function in `/shared` — this is the single entrypoint the FastAPI service will call, and the only place Flow logic is invoked from (see Section 3).
- [ ] Unit test the Orchestrator in isolation with a handful of sample queries (pure HR, pure Finance, mixed, ambiguous) to validate routing before connecting specialist crews fully.

## 3. Create the Shared Backend API

- [ ] Scaffold a minimal FastAPI app (`/shared/api.py`) exposing a `POST /chat` endpoint accepting `{platform, user_id, message}` and returning `{response, metadata}`.
- [ ] Inside the endpoint, call `run_orchestrator()` from Section 2, passing in the correct session state for that `(platform, user_id)` pair.
- [ ] Implement session state storage keyed by `(platform, user_id)` — start with a simple in-memory dict or SQLite table, upgrade later if needed.
- [ ] Add a lightweight session-lookup/creation helper so a brand-new `user_id` gets fresh state, and returning users resume their existing conversation.
- [ ] Add basic request validation (Pydantic models) and error responses (e.g. 500 with a clean message if the Flow throws).
- [ ] Add a `GET /health` endpoint for quick sanity checks while developing/demoing.
- [ ] Run the API locally via `uvicorn` and test it directly with `curl`/Postman before wiring up either UI, to confirm the Flow works end-to-end over HTTP.
- [ ] (Optional, if time allows) Add simple logging per request — which platform/user, which specialist crews were invoked, response time — useful both for debugging and demoing.

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
