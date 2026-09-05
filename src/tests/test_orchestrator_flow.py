from crews.orchestrator.schemas import RephrasedQuery, RoutingDecision
from flows.orchestrator_flow import OrchestratorFlow


def _decision(
    route_type,
    specialists=None,
    rephrased_queries=None,
    direct_answer=None,
    clarifying_question=None,
):
    return RoutingDecision(
        route_type=route_type,
        specialists=specialists or [],
        rephrased_queries=[
            RephrasedQuery(specialist=specialist, query=query)
            for specialist, query in (rephrased_queries or {}).items()
        ],
        direct_answer=direct_answer,
        clarifying_question=clarifying_question,
    )


def _patch_route(monkeypatch, decision: RoutingDecision):
    monkeypatch.setattr(
        "flows.orchestrator_flow.orchestrator_agent.route",
        lambda user_input, business_context: decision,
    )


def _patch_synthesize(monkeypatch, response: str):
    monkeypatch.setattr(
        "flows.orchestrator_flow.orchestrator_agent.synthesize",
        lambda user_input, specialist_outputs: response,
    )


def test_pure_hr_query(monkeypatch):
    _patch_route(
        monkeypatch,
        _decision(
            "delegate",
            specialists=["hr"],
            rephrased_queries={"hr": "How many employees are currently on staff?"},
        ),
    )
    _patch_synthesize(monkeypatch, "combined hr answer")

    flow = OrchestratorFlow()
    flow.kickoff(inputs={"user_input": "How many employees are on the roster?"})

    assert flow.state.invoked_specialists == ["hr"]
    assert flow.state.active_agent_outputs["hr"] == (
        "[HR placeholder] would respond to: How many employees are currently on staff?"
    )
    assert flow.state.final_response == "combined hr answer"


def test_pure_finance_query(monkeypatch):
    _patch_route(
        monkeypatch,
        _decision(
            "delegate",
            specialists=["finance"],
            rephrased_queries={"finance": "What is the budget for this expense?"},
        ),
    )
    _patch_synthesize(monkeypatch, "combined finance answer")

    flow = OrchestratorFlow()
    flow.kickoff(inputs={"user_input": "What's our budget for this expense?"})

    assert flow.state.invoked_specialists == ["finance"]
    assert flow.state.final_response == "combined finance answer"


def test_mixed_hr_and_finance_query(monkeypatch):
    _patch_route(
        monkeypatch,
        _decision(
            "delegate",
            specialists=["hr", "finance"],
            rephrased_queries={
                "hr": "Update the employee roster.",
                "finance": "Check the budget for this expense.",
            },
        ),
    )
    _patch_synthesize(monkeypatch, "combined hr+finance answer")

    flow = OrchestratorFlow()
    flow.kickoff(inputs={"user_input": "Update the roster and check the budget"})

    assert set(flow.state.invoked_specialists) == {"hr", "finance"}
    assert flow.state.final_response == "combined hr+finance answer"


def test_clarify_path(monkeypatch):
    _patch_route(
        monkeypatch,
        _decision(
            "clarify",
            clarifying_question="Could you clarify what you need help with?",
        ),
    )

    flow = OrchestratorFlow()
    flow.kickoff(inputs={"user_input": "Hey, can you help me out?"})

    assert flow.state.invoked_specialists == []
    assert flow.state.final_response == "Could you clarify what you need help with?"


def test_direct_path(monkeypatch):
    _patch_route(
        monkeypatch,
        _decision(
            "direct",
            direct_answer="Hi there! I'm the orchestrator for this assistant.",
        ),
    )

    flow = OrchestratorFlow()
    flow.kickoff(inputs={"user_input": "Hi, who are you?"})

    assert flow.state.invoked_specialists == []
    assert flow.state.final_response == "Hi there! I'm the orchestrator for this assistant."
