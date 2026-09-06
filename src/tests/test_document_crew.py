"""
test_document_crew.py
Tests for the Document specialist crew (crews/document/) and the Document
Team Lead dispatch logic that lives in OrchestratorFlow
(flows/orchestrator_flow.py). No LLM API key needed anywhere here: the pure
Python pieces (financial forecast math, escalation gate) are exercised
directly, and the dispatch tests monkeypatch each specialist Agent's
kickoff() so no real model call happens.
"""
from __future__ import annotations

import json

from crews.document.tools.financial_tools import generate_financial_forecast
from crews.document import escalation
from crews.document.schemas import DocumentRoutingDecision, DocumentType
from flows.orchestrator_flow import OrchestratorFlow


def test_financial_forecast_is_deterministic():
    a = json.loads(generate_financial_forecast.run(5000, 0.06, 0.35, 8000, 50000))
    b = json.loads(generate_financial_forecast.run(5000, 0.06, 0.35, 8000, 50000))
    assert len(a["months"]) == len(b["months"]) == 36
    assert a["monthly_burn_rate_sgd"] == b["monthly_burn_rate_sgd"]
    assert a["break_even_month_index"] == b["break_even_month_index"]


def test_escalation_gate_blocks_until_resolved():
    escalation._STORE.clear()
    session_id = "s_test"
    assert not escalation.has_pending_escalations(session_id)

    req = escalation.request_escalation(
        session_id, DocumentType.MODEL_CONSTITUTION, "/tmp/x.docx", "needs sign-off"
    )
    assert escalation.has_pending_escalations(session_id)
    assert len(escalation.get_pending(session_id)) == 1

    escalation.resolve_escalation(session_id, req.escalation_id, approve=True, reviewer_id="r1")
    assert not escalation.has_pending_escalations(session_id)
    resolved = escalation.get_resolved_since_last_check(session_id)
    assert resolved[0].status.value == "approved"


# ---------------------------------------------------------------------------
# Document Team Lead dispatch logic (flows/orchestrator_flow.py)
# ---------------------------------------------------------------------------


class _FakeKickoffResult:
    def __init__(self, raw=None):
        self.raw = raw


class _FakeAgent:
    """Stands in for a crewai.Agent. Agent is a pydantic model and rejects
    arbitrary attribute assignment, so tests monkeypatch the module-level
    name orchestrator_flow.py holds rather than `.kickoff` on the instance.
    """

    def __init__(self, result):
        self._result = result
        self.calls: list[str] = []

    def kickoff(self, prompt, **kwargs):
        self.calls.append(prompt)
        return self._result


def _routing_decision(**overrides) -> DocumentRoutingDecision:
    base = dict(
        route_type="dispatch",
        specialist="statutory",
        document_types=[],
        grant_scheme=None,
        requested_amount_sgd=None,
        clarifying_question=None,
    )
    base.update(overrides)
    return DocumentRoutingDecision(**base)


def test_dispatch_statutory_renders_from_knowledge_base(monkeypatch):
    """company_profile.json ships in the repo (knowledge/documents/) — the
    specialist should load and use it directly, no business_context needed.
    """
    fake_statutory = _FakeAgent(_FakeKickoffResult(raw="Rendered the Model Constitution."))
    monkeypatch.setattr("flows.orchestrator_flow.statutory_compliance_agent", fake_statutory)

    flow = OrchestratorFlow()
    output = flow._dispatch_statutory(
        _routing_decision(document_types=["model_constitution"])
    )

    assert output == "Rendered the Model Constitution."
    assert len(fake_statutory.calls) == 1
    # The real company_profile.json's data should have been injected into the prompt.
    assert "Acme Robotics" in fake_statutory.calls[0]


def test_dispatch_statutory_rejects_invalid_knowledge_base_fixture(monkeypatch):
    monkeypatch.setattr("flows.orchestrator_flow.load_company_profile", lambda: {})
    fake_statutory = _FakeAgent(_FakeKickoffResult(raw="ignored"))
    monkeypatch.setattr("flows.orchestrator_flow.statutory_compliance_agent", fake_statutory)

    flow = OrchestratorFlow()
    output = flow._dispatch_statutory(_routing_decision())

    assert "Internal error" in output
    assert fake_statutory.calls == []


def test_dispatch_financial_uses_knowledge_base_assumptions(monkeypatch):
    fake_financial = _FakeAgent(_FakeKickoffResult(raw="Forecast generated."))
    monkeypatch.setattr("flows.orchestrator_flow.financial_synthesizer_agent", fake_financial)

    flow = OrchestratorFlow()
    output = flow._dispatch_financial()

    assert output == "Forecast generated."
    assert len(fake_financial.calls) == 1
    # The real financial_assumptions.json's data should have been injected.
    assert "8000" in fake_financial.calls[0]  # starting_monthly_revenue_sgd


def test_dispatch_grant_auto_chains_financial_forecast(monkeypatch):
    forecast_json = json.dumps(
        {
            "months": [],
            "currency": "SGD",
            "monthly_burn_rate_sgd": 0.0,
            "runway_months": -1,
            "break_even_month_index": None,
            "assumptions": {},
        }
    )
    monkeypatch.setattr(
        "flows.orchestrator_flow.financial_synthesizer_agent",
        _FakeAgent(_FakeKickoffResult(raw=f"Here is the forecast: {forecast_json}")),
    )

    fake_grant = _FakeAgent(_FakeKickoffResult(raw="Grant package compiled."))
    monkeypatch.setattr("flows.orchestrator_flow.grant_strategist_agent", fake_grant)

    flow = OrchestratorFlow()
    assert flow.state.business_context.get("financial_forecast") is None

    output = flow._dispatch_grant(
        _routing_decision(
            specialist="grant",
            grant_scheme="startup_sg_founder",
            requested_amount_sgd=50000,
        )
    )

    assert output == "Grant package compiled."
    assert len(fake_grant.calls) == 1
    assert flow.state.business_context.get("financial_forecast") is not None
