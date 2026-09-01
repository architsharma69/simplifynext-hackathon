# tests

## `__init__.py`
Empty. Just marks this folder as a Python package.

## `test_orchestrator_flow.py`
Runs the flow end-to-end with sample questions, no mocking needed since the specialists are already placeholders.

- `test_pure_hr_query()` — Confirms an HR-flavored question only triggers the HR specialist, and its placeholder text shows up in the answer.
- `test_pure_finance_query()` — Same check, but for a Finance-flavored question.
- `test_mixed_hr_and_finance_query()` — Confirms a question hitting both HR and Finance keywords triggers both specialists and combines their answers.
- `test_ambiguous_query_asks_for_clarification()` — Confirms a question matching no keywords triggers no specialists and returns the clarifying question instead.

## `test_entrypoint.py`
Checks `run_orchestrator`'s memory behaves correctly across turns.

- `test_session_state_only_contains_cross_turn_fields()` — Confirms the state handed back for "next time" only has the fields meant to persist, not per-turn leftovers.
- `test_conversation_history_grows_across_calls()` — Confirms asking a second question, using the first call's saved state, adds to (not replaces) the conversation history.
- `test_per_turn_fields_do_not_leak_between_calls()` — Confirms which specialists ran on the first question doesn't carry over and affect an unrelated second question.

## `test_api.py`
Hits the FastAPI app directly (no real server needed) to check its endpoints.

- `test_health()` — Confirms `/health` responds with a 200 and the expected status message.
- `test_chat_routes_to_hr()` — Confirms an HR-flavored message sent to `/chat` comes back listing HR as an invoked specialist.
- `test_chat_session_persists_across_calls()` — Confirms two messages from the same user in a row both end up saved in that user's conversation history.
- `test_chat_missing_field_returns_422()` — Confirms an incomplete request (missing the message) is rejected with a 422 validation error.
- `test_chat_error_returns_clean_envelope()` — Confirms that if the orchestrator itself fails, the API still returns a clean, friendly error response instead of crashing or leaking a stack trace.