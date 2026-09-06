"""
api/documents.py
Maps opaque document_ids to the local file paths documents get rendered to
(Config.DOCUMENT_OUTPUT_DIR), so /chat responses and Streamlit never see a
raw server-side path — only an id to hand back to GET /documents/{id}.

In-memory dict for illustration, same pattern as api/sessions.py — swap for
Redis/Postgres in production.
"""
from __future__ import annotations

import uuid

_DOCUMENTS: dict[str, str] = {}


def register_document(file_path: str) -> str:
    document_id = uuid.uuid4().hex
    _DOCUMENTS[document_id] = file_path
    return document_id


def get_document_path(document_id: str) -> str | None:
    return _DOCUMENTS.get(document_id)
