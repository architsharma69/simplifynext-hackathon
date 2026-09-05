"""
escalation.py
The human escalation / verification gate. This is deliberately NOT part of
any CrewAI Agent's toolset for *deciding* approval — an LLM should never be
the one that approves a legal filing. Instead:

  1. A document-producing tool calls `request_escalation(...)` after it
     renders a document. This flips the item to PENDING_REVIEW and returns
     immediately (non-blocking) — CrewAI Flows are synchronous per-step, so
     we do NOT sleep/poll inside a Task. The Flow instead persists its state
     and exits the run; a human decision resumes it later via the API.
  2. A reviewer-facing FastAPI endpoint calls `resolve_escalation(...)` when
     a human approves/rejects/requests changes.
  3. On the *next* user message for that session, the Flow's entry point
     checks `has_pending_escalations(state)` first and short-circuits back
     to the human's decision before doing anything else.

Storage here is an in-memory dict for illustration. Swap `_STORE` for a
Redis/Postgres-backed repository in production — the important part is that
escalation state is queryable independently of any single Flow run, since
the reviewer and the end user are different people hitting the API at
different times.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from models import DocumentType, EscalationRequest, EscalationStatus
from flows.state import HermesState

# session_id -> {escalation_id -> EscalationRequest}
_STORE: dict[str, dict[str, EscalationRequest]] = {}


def request_escalation(
    state: HermesState,
    document_type: DocumentType,
    file_path: str,
    reason: str,
) -> EscalationRequest:
    """Create a PENDING_REVIEW escalation and attach it to Flow state."""
    req = EscalationRequest(
        escalation_id=str(uuid.uuid4()),
        session_id=state.session_id,
        document_type=document_type,
        file_path=file_path,
        reason=reason,
    )
    _STORE.setdefault(state.session_id, {})[req.escalation_id] = req
    state.pending_escalations.append(req)
    state.note(f"Escalation requested for {document_type.value}: {reason}")
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


def has_pending_escalations(state: HermesState) -> bool:
    bucket = _STORE.get(state.session_id, {})
    return any(r.status == EscalationStatus.PENDING_REVIEW for r in bucket.values())


def sync_state_escalations(state: HermesState) -> None:
    """Refresh state.pending_escalations from the store (call at Flow re-entry)."""
    bucket = _STORE.get(state.session_id, {})
    state.pending_escalations = [
        r for r in bucket.values() if r.status == EscalationStatus.PENDING_REVIEW
    ]


def get_resolved_since_last_check(state: HermesState) -> list[EscalationRequest]:
    bucket = _STORE.get(state.session_id, {})
    return [r for r in bucket.values() if r.status != EscalationStatus.PENDING_REVIEW]
