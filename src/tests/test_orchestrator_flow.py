import json

from crews.document.schemas import DocumentRoutingDecision
from crews.orchestrator.schemas import RephrasedQuery, RoutingDecision
from flows.orchestrator_flow import OrchestratorFlow


class _FakeKickoffResult:
    """Stands in for CrewAI's Agent.kickoff() return value in tests."""

    def __init__(self, raw=None, pydantic=None):
        self.raw = raw
        self.pydantic = pydantic


class _FakeAgent:
    """Stands in for a crewai.Agent in tests. Agent is a pydantic model, so
    its instances reject arbitrary attribute assignment (`.kickoff = ...`
    fails) — instead we monkeypatch the module-level name that
    orchestrator_flow.py holds, swapping in one of these.
    """

    def __init__(self, result):
        self._result = result
        self.calls: list[str] = []

    def kickoff(self, prompt, **kwargs):
        self.calls.append(prompt)
        return self._result


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


def test_pure_document_query(monkeypatch):
    _patch_route(
        monkeypatch,
        _decision(
            "delegate",
            specialists=["document"],
            rephrased_queries={"document": "Build our 3-year financial forecast."},
        ),
    )
    _patch_synthesize(monkeypatch, "combined document answer")

    routing_decision = DocumentRoutingDecision(
        route_type="dispatch",
        specialist="financial",
        document_types=[],
        grant_scheme=None,
        requested_amount_sgd=None,
        extracted_fields_json=json.dumps(
            {
                "financial_assumptions": {
                    "starting_monthly_revenue_sgd": 5000,
                    "monthly_revenue_growth_pct": 0.05,
                    "cogs_pct_of_revenue": 0.3,
                    "fixed_monthly_opex_sgd": 2000,
                    "starting_cash_sgd": 20000,
                }
            }
        ),
        clarifying_question=None,
    )
    monkeypatch.setattr(
        "flows.orchestrator_flow.document_team_lead_agent",
        _FakeAgent(_FakeKickoffResult(pydantic=routing_decision)),
    )
    monkeypatch.setattr(
        "flows.orchestrator_flow.financial_synthesizer_agent",
        _FakeAgent(_FakeKickoffResult(raw="Forecast generated. Burn rate is low.")),
    )

    flow = OrchestratorFlow()
    flow.kickoff(inputs={"user_input": "Can you build our financial forecast?"})

    assert flow.state.invoked_specialists == ["document"]
    assert flow.state.active_agent_outputs["document"] == "Forecast generated. Burn rate is low."
    assert flow.state.final_response == "combined document answer"


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
