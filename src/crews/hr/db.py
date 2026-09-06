"""
crews/hr/db.py
SQLite ledger for the HR / Workload Manager crew. Four tables and the date
helpers everything else builds on. No CrewAI here, no LLM here — this layer
must be correct before any agent exists.

Ported from the standalone workload_manager prototype (plan/workload_manager/db.py)
with no logic changes — only the import path changed, since it now lives at
crews.hr.db instead of a flat top-level module.
"""

import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "workload.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS people (
    id                  INTEGER PRIMARY KEY,
    name                TEXT NOT NULL UNIQUE,
    role                TEXT NOT NULL,
    skills              TEXT NOT NULL DEFAULT '',   -- comma separated
    weekly_capacity_hrs REAL NOT NULL DEFAULT 40,
    timezone            TEXT NOT NULL DEFAULT 'Asia/Singapore',
    contact_handle      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    assignee_id INTEGER REFERENCES people(id),
    est_hours   REAL NOT NULL,
    due_date    TEXT NOT NULL,                      -- ISO YYYY-MM-DD
    status      TEXT NOT NULL DEFAULT 'unassigned', -- unassigned|in_progress|done|cancelled
    priority    TEXT NOT NULL DEFAULT 'normal',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS workload_log (
    person_id       INTEGER NOT NULL REFERENCES people(id),
    week            TEXT NOT NULL,                  -- ISO week, e.g. 2026-W36
    assigned_hours  REAL NOT NULL DEFAULT 0,
    actual_hours    REAL,
    overload_flag   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (person_id, week)
);

CREATE TABLE IF NOT EXISTS wellbeing_events (
    id         INTEGER PRIMARY KEY,
    person_id  INTEGER NOT NULL REFERENCES people(id),
    type       TEXT NOT NULL,       -- leave|sick|overloaded|flagged|override_approved
    note       TEXT NOT NULL DEFAULT '',
    start_date TEXT,                -- for leave/sick
    end_date   TEXT,
    ts         TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(reset: bool = False) -> None:
    if reset and DB_PATH.exists():
        DB_PATH.unlink()
    with connect() as conn:
        conn.executescript(SCHEMA)


# --------------------------------------------------------------------------
# Date helpers.  One definition of "week", used everywhere, so the forecast
# and the safety check can never disagree about which week a date is in.
# --------------------------------------------------------------------------

def week_of(d) -> str:
    """'2026-09-04' or a date -> '2026-W36' (ISO week)."""
    if isinstance(d, str):
        d = date.fromisoformat(d)
    return f"{d.isocalendar().year}-W{d.isocalendar().week:02d}"


def monday_of(week: str) -> date:
    """'2026-W36' -> the Monday of that week."""
    year, wk = week.split("-W")
    return date.fromisocalendar(int(year), int(wk), 1)


def next_n_weeks(n: int, start: date | None = None) -> list[str]:
    start = start or date.today()
    return [week_of(start + timedelta(weeks=i)) for i in range(n)]


def previous_week(week: str) -> str:
    return week_of(monday_of(week) - timedelta(days=7))


def is_out_of_hours(d) -> bool:
    """True if the deadline lands on a weekend."""
    if isinstance(d, str):
        d = date.fromisoformat(d)
    return d.weekday() >= 5
