"""
test_document_crew.py
Standalone tests for the Document specialist crew (crews/document/), with
no dependency on flows/, api/, or an LLM API key. Exercises the parts that
are pure Python: the financial forecast math, the escalation gate, and the
schemas they're built on.
"""
from __future__ import annotations

import json

from crews.document.tools.financial_tools import generate_financial_forecast
from crews.document import escalation
from crews.document.schemas import DocumentType


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
