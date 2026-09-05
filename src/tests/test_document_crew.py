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
        extracted_fields_json="{}",
        clarifying_question=None,
    )
    base.update(overrides)
    return DocumentRoutingDecision(**base)


def _complete_company_profile() -> dict:
    return {
        "proposed_company_name": "Acme Robotics",
        "registered_address": "1 Raffles Place, Singapore",
        "principal_activity_ssic_code": "62010",
        "directors": [
            {
                "full_name": "Jane Tan",
                "nric_or_passport": "S1234567A",
                "nationality": "Singaporean",
                "residential_address": "2 Orchard Rd, Singapore",
                "is_resident_director": True,
            }
        ],
        "shareholders": [
            {"full_name": "Jane Tan", "id_number": "S1234567A", "shares_held": 100}
        ],
        "paid_up_capital_sgd": 1000,
    }


def test_dispatch_statutory_asks_for_missing_fields_without_calling_agent(monkeypatch):
    fake_statutory = _FakeAgent(_FakeKickoffResult(raw="ignored"))
    monkeypatch.setattr("flows.orchestrator_flow.statutory_compliance_agent", fake_statutory)

    flow = OrchestratorFlow()
    flow.state.business_context = {"company_profile": {}}
    output = flow._dispatch_statutory(_routing_decision(specialist="statutory"))

    assert "I still need" in output
    assert fake_statutory.calls == []


def test_dispatch_statutory_renders_when_complete(monkeypatch):
    fake_statutory = _FakeAgent(_FakeKickoffResult(raw="Rendered the Model Constitution."))
    monkeypatch.setattr("flows.orchestrator_flow.statutory_compliance_agent", fake_statutory)

    flow = OrchestratorFlow()
    flow.state.business_context = {"company_profile": _complete_company_profile()}
    output = flow._dispatch_statutory(
        _routing_decision(document_types=["model_constitution"])
    )

    assert output == "Rendered the Model Constitution."


def test_dispatch_financial_asks_for_missing_assumptions_without_calling_agent(monkeypatch):
    fake_financial = _FakeAgent(_FakeKickoffResult(raw="ignored"))
    monkeypatch.setattr("flows.orchestrator_flow.financial_synthesizer_agent", fake_financial)

    flow = OrchestratorFlow()
    flow.state.business_context = {
        "financial_assumptions": {"starting_monthly_revenue_sgd": 5000}
    }
    output = flow._dispatch_financial()

    assert "I still need" in output
    assert fake_financial.calls == []


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
    flow.state.business_context = {
        "financial_assumptions": {
            "starting_monthly_revenue_sgd": 5000,
            "monthly_revenue_growth_pct": 0.05,
            "cogs_pct_of_revenue": 0.3,
            "fixed_monthly_opex_sgd": 2000,
            "starting_cash_sgd": 20000,
        },
        "company_profile": _complete_company_profile(),
        "headcount_plan": {"lines": []},
        "narrative_sections": {
            "problem_statement": "x" * 100,
            "solution": "x" * 100,
            "market_opportunity": "x" * 100,
            "founder_background": "x" * 100,
            "use_of_funds": "x" * 100,
        },
        "requested_amount_sgd": 50000,
    }
    output = flow._dispatch_grant(
        _routing_decision(specialist="grant", grant_scheme="startup_sg_founder")
    )

    assert output == "Grant package compiled."
    assert len(fake_grant.calls) == 1
    assert flow.state.business_context.get("financial_forecast") is not None
