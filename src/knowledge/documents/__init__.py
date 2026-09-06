"""
knowledge/documents/__init__.py
Sample reference data for the document specialist team, kept as JSON files
in the repo for the hackathon instead of being collected live via
conversation. Each document specialist loads exactly the file it needs and
the content is injected directly into its prompt (see
flows/orchestrator_flow.py's _dispatch_* methods) — no tool call, no flow
state.
"""
from __future__ import annotations

import json
from pathlib import Path

_DIR = Path(__file__).resolve().parent


def _load(filename: str) -> dict:
    return json.loads((_DIR / filename).read_text())


def load_company_profile() -> dict:
    return _load("company_profile.json")


def load_financial_assumptions() -> dict:
    return _load("financial_assumptions.json")


def load_grant_narrative(scheme: str) -> dict:
    narratives = _load("grant_narrative.json")
    return narratives[scheme]


def load_headcount_plan() -> dict:
    return _load("headcount_plan.json")
