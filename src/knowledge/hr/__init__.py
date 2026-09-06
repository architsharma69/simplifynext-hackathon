"""
knowledge/hr/__init__.py
Sample employee/roster data for the HR specialist, kept as a JSON file in the
repo for the hackathon instead of being seeded into a SQLite ledger. Mirrors
knowledge/documents/__init__.py's pattern exactly: one loader, plain
json.loads, no business logic here.

team_roster.json's dates are offsets (due_offset_days, start_offset_days, ...)
relative to the Monday of the current week rather than fixed calendar dates,
so the fixture never goes stale. crews/hr/roster.py resolves those offsets
into real ISO dates and does everything else (workload math, the safety
guardrail's reads) -- this module only loads the raw file.
"""
from __future__ import annotations

import json
from pathlib import Path

_DIR = Path(__file__).resolve().parent


def _load(filename: str) -> dict:
    return json.loads((_DIR / filename).read_text())


def load_team_roster() -> dict:
    return _load("team_roster.json")
