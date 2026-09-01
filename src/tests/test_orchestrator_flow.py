from flows.orchestrator_flow import OrchestratorFlow


def test_pure_hr_query():
    flow = OrchestratorFlow()
    flow.kickoff(inputs={"user_input": "How many employees are on the roster?"})

    assert flow.state.invoked_specialists == ["hr"]
    assert "[HR placeholder]" in flow.state.final_response


def test_pure_finance_query():
    flow = OrchestratorFlow()
    flow.kickoff(inputs={"user_input": "What's our budget for this expense?"})

    assert flow.state.invoked_specialists == ["finance"]
    assert "[Finance placeholder]" in flow.state.final_response


def test_mixed_hr_and_finance_query():
    flow = OrchestratorFlow()
    flow.kickoff(inputs={"user_input": "Update the employee roster and check the budget for this expense"})

    assert set(flow.state.invoked_specialists) == {"hr", "finance"}
    assert "[HR placeholder]" in flow.state.final_response
    assert "[Finance placeholder]" in flow.state.final_response


def test_ambiguous_query_asks_for_clarification():
    flow = OrchestratorFlow()
    flow.kickoff(inputs={"user_input": "Hey, can you help me out?"})

    assert flow.state.invoked_specialists == []
    assert flow.state.final_response == flow.state.routing_decision["clarifying_question"]
