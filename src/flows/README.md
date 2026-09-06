# flows

## `__init__.py`
Empty. Just marks this folder as a Python package.

## `state.py`
Defines `OrchestratorState`, the shared data object every step of the flow reads and writes. No functions, just fields:

- `conversation_history` — Past user messages and the responses given, so the orchestrator has memory across turns.
- `active_agent_outputs` — The raw text each specialist crew returned for the current question.
- `pending_actions` — Reserved for actions still waiting on something (e.g. human approval). Not used yet.
- `business_context` — Background info about the business asking questions, meant to inform routing and answers.
- `user_input` — The question the user just asked, for this turn only.
- `routing_decision` — Which specialist(s) got chosen this turn, or the clarifying question if none did.
- `invoked_specialists` — The list of specialists that actually ran this turn.
- `final_response` — The single combined answer sent back to the user.

## `placeholders.py`
Stand-in logic for the specialists that don't exist yet. HR, Document and the Orchestrator itself are real now and are called directly, so only two placeholders are left.

- `run_finance(sub_query)` — Fake Finance specialist. Echoes the question back with a `[Finance placeholder]` label instead of really answering it.
- `run_consultant()` — Fake Consultant specialist. Always returns a canned "no improvements yet" message.

## `orchestrator_flow.py`
The control flow itself, built with CrewAI's `Flow`.

- `_truncate(value, length)` — Shortens a string for cleaner log lines, adding `...` if it got cut off.
- `OrchestratorFlow.receive_input()` — The flow's starting point. Just logs that a new question came in.
- `OrchestratorFlow.classify_intent_step()` — Calls the placeholder routing logic and saves the result (which specialists, or a clarifying question) into the flow's state.
- `OrchestratorFlow.check_confidence()` — Reads the routing decision and sends the flow down the "ask for clarification" path or the "call specialists" path.
- `OrchestratorFlow.ask_clarification()` — Sets the final response to the clarifying question, used when routing couldn't tell what was being asked.
- `OrchestratorFlow.route_hr()` — Runs the real HR workload-manager crew (`crews/hr/`) via `_run_hr_team()` and saves its answer, but only if HR was chosen for this question; otherwise does nothing.
- `OrchestratorFlow.route_finance()` — Same shape as `route_hr`, but still calls the Finance placeholder.
- `OrchestratorFlow.route_document()` — Same as `route_hr`, but for the Document specialist.
- `OrchestratorFlow.synthesize_step()` — Once all three specialist branches have run (even the ones that did nothing), combines their outputs into the final response.
- `OrchestratorFlow.run_consultant_review()` — A separate, manually-triggered check-in from the Consultant specialist. Not run automatically on every question.