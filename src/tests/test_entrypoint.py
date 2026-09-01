from api.entrypoint import CROSS_TURN_FIELDS, run_orchestrator


def test_session_state_only_contains_cross_turn_fields():
    result = run_orchestrator("How many employees are on the roster?")

    assert set(result["session_state"].keys()) == set(CROSS_TURN_FIELDS)


def test_conversation_history_grows_across_calls():
    first = run_orchestrator("How many employees are on the roster?")
    assert len(first["session_state"]["conversation_history"]) == 1

    second = run_orchestrator("What's our budget for this expense?", first["session_state"])
    assert len(second["session_state"]["conversation_history"]) == 2


def test_per_turn_fields_do_not_leak_between_calls():
    first = run_orchestrator("How many employees are on the roster?")
    assert first["invoked_specialists"] == ["hr"]

    second = run_orchestrator("Hey, can you help me out?", first["session_state"])
    assert second["invoked_specialists"] == []