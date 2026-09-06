"""
escalation.py
The human escalation / verification gate. This is deliberately NOT part of
any CrewAI Agent's toolset for *deciding* approval — an LLM should never be
the one that approves a legal filing. Instead:

  1. A document-producing tool calls `request_escalation(...)` after it
     renders a document. This flips the item to PENDING_REVIEW and returns
     immediately (non-blocking).
  2. A reviewer-facing FastAPI endpoint calls `resolve_escalation(...)` when
     a human approves/rejects/requests changes.
  3. On the *next* user message for that session, whatever drives this crew
     checks `has_pending_escalations(session_id)` first and short-circuits
     back to the human's decision before doing anything else.

Storage here is an in-memory dict for illustration. Swap `_STORE` for a
Redis/Postgres-backed repository in production.

NOTE: this module intentionally works off a plain `session_id: str` rather
than a shared Flow-state object (there's no HermesState in this repo — the
top-level Flow uses OrchestratorState, which doesn't carry escalation
fields yet). Keeping this decoupled means the document crew doesn't need
to touch flows/state.py to function standalone; if/when escalation state
should be visible to the top-level Flow, that's an explicit integration
step, not an implicit dependency.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from crews.document.schemas import DocumentType, EscalationRequest, EscalationStatus

# session_id -> {escalation_id -> EscalationRequest}
_STORE: dict[str, dict[str, EscalationRequest]] = {}


def request_escalation(
    session_id: str,
    document_type: DocumentType,
    file_path: str,
    reason: str,
) -> EscalationRequest:
    """Create a PENDING_REVIEW escalation for this session."""
    req = EscalationRequest(
        escalation_id=str(uuid.uuid4()),
        session_id=session_id,
        document_type=document_type,
        file_path=file_path,
        reason=reason,
    )
    _STORE.setdefault(session_id, {})[req.escalation_id] = req
    return req


def resolve_escalation(
    session_id: str,
    escalation_id: str,
    approve: bool,
    reviewer_id: str,
    comment: Optional[str] = None,
) -> EscalationRequest:
    """Called by the reviewer-facing endpoint, not by any agent/tool."""
    bucket = _STORE.get(session_id, {})
    req = bucket.get(escalation_id)
    if req is None:
        raise KeyError(f"No escalation {escalation_id} for session {session_id}")
    req.status = EscalationStatus.APPROVED if approve else EscalationStatus.REJECTED
    req.reviewer_id = reviewer_id
    req.reviewer_comment = comment
    req.decided_at = datetime.utcnow()
    return req


def has_pending_escalations(session_id: str) -> bool:
    bucket = _STORE.get(session_id, {})
    return any(r.status == EscalationStatus.PENDING_REVIEW for r in bucket.values())


def get_pending(session_id: str) -> list[EscalationRequest]:
    bucket = _STORE.get(session_id, {})
    return [r for r in bucket.values() if r.status == EscalationStatus.PENDING_REVIEW]


def get_resolved_since_last_check(session_id: str) -> list[EscalationRequest]:
    bucket = _STORE.get(session_id, {})
    return [r for r in bucket.values() if r.status != EscalationStatus.PENDING_REVIEW]
