"""
crews/hr/roster.py
Read-side data access for the HR / Workload Manager crew, backed by the
static JSON fixture at knowledge/hr/team_roster.json instead of a SQLite
ledger. Replaces db.py and the read half of the old ledger.py.

The fixture's dates are offsets (due_offset_days, start_offset_days, ...)
relative to the Monday of the CURRENT week, resolved to absolute ISO dates
here at call time -- that is what keeps the demo (Priya overloaded, Wei
Ling on leave Thu/Fri) correct no matter what day it's actually run, with
no seed script and no database to regenerate.

Nothing here writes anything. Every function recomputes straight from the
fixture, every call -- there is no session state to go stale. See
crews/hr/tools/*.py for how the (stateless) write-shaped tools work now.
"""
from __future__ import annotations

from datetime import date, timedelta

from knowledge.hr import load_team_roster

OPEN_STATUSES = ("unassigned", "in_progress")


class RosterError(Exception):
    """Raised for bad input. Callers turn this into a message for the
    model, never into a crash. Mirrors the old ledger.LedgerError's role."""


# ==========================================================================
# date helpers (ported from db.py, unchanged)
# ==========================================================================

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


def is_out_of_hours(d) -> bool:
    """True if the deadline lands on a weekend."""
    if isinstance(d, str):
        d = date.fromisoformat(d)
    return d.weekday() >= 5


def _this_monday(today: date) -> date:
    return today - timedelta(days=today.weekday())


def _resolve_date(offset_days: int, today: date) -> str:
    return (_this_monday(today) + timedelta(days=offset_days)).isoformat()


# ==========================================================================
# fixture resolution -- turns offsets into real dates, once per call
# ==========================================================================

def _people(today: date | None = None) -> list[dict]:
    today = today or date.today()
    raw = load_team_roster()
    people = []
    for p in raw["people"]:
        leave = [
            {
                "start_date": _resolve_date(entry["start_offset_days"], today),
                "end_date": _resolve_date(entry["end_offset_days"], today),
                "note": entry.get("note", ""),
            }
            for entry in p.get("leave", [])
        ]
        people.append({**p, "leave": leave})
    return people


def _tasks(today: date | None = None) -> list[dict]:
    today = today or date.today()
    raw = load_team_roster()
    return [
        {**t, "id": i + 1, "due_date": _resolve_date(t["due_offset_days"], today)}
        for i, t in enumerate(raw["tasks"])
    ]


# ==========================================================================
# reads
# ==========================================================================

def get_team_roster(today: date | None = None) -> list[dict]:
    return sorted(_people(today), key=lambda p: p["name"])


def get_person(name: str, today: date | None = None) -> dict | None:
    """Look up by name, case-insensitively. Returns None if absent."""
    needle = str(name).strip().lower()
    for p in _people(today):
        if p["name"].lower() == needle:
            return p
    return None


def on_leave(person_name: str, day: str, today: date | None = None) -> bool:
    person = get_person(person_name, today)
    if not person:
        return False
    return any(l["start_date"] <= day <= l["end_date"] for l in person["leave"])


def assigned_hours(person_name: str, week: str, today: date | None = None) -> float:
    """Committed hours for one person in one ISO week, from open tasks.

    Single source of truth for 'how loaded is this person'. The forecast
    and the safety check both call this, so they cannot drift apart.
    """
    rows = [
        t for t in _tasks(today)
        if t.get("assignee") == person_name and t["status"] in OPEN_STATUSES
    ]
    return round(sum(r["est_hours"] for r in rows if week_of(r["due_date"]) == week), 2)


def effective_capacity(person_name: str, week: str, today: date | None = None) -> float:
    """Weekly capacity, reduced pro-rata for any logged leave in that week."""
    person = get_person(person_name, today)
    if not person:
        raise RosterError(f"No one named '{person_name}' is in the roster.")
    capacity = person["weekly_capacity_hrs"]
    monday = monday_of(week)
    working_days = [monday + timedelta(days=i) for i in range(5)]
    off = sum(1 for d in working_days if on_leave(person_name, d.isoformat(), today))
    if off == 0:
        return capacity
    return round(capacity * (5 - off) / 5, 2)


def overload_streak(person_name: str, week: str, today: date | None = None) -> int:
    """Consecutive weeks BEFORE `week` this person was overloaded.

    Sourced from the fixture's static `overloaded_streak_weeks` field rather
    than a real per-week history, so it's the same count no matter which
    near-term week is being checked -- there's no history to walk back
    through any more, just the snapshot fact "this is how overloaded they
    already are." The `week` argument is kept for signature parity with the
    read functions above (and in case a future fixture wants to vary it).
    """
    person = get_person(person_name, today)
    return int(person.get("overloaded_streak_weeks", 0)) if person else 0


def get_person_workload(name: str, week: str | None = None, today: date | None = None) -> dict:
    today = today or date.today()
    person = get_person(name, today)
    if not person:
        raise RosterError(
            f"No one named '{name}' is in the roster. "
            f"The team is: {', '.join(p['name'] for p in get_team_roster(today))}."
        )
    week = week or week_of(today)
    hours = assigned_hours(person["name"], week, today)
    capacity = effective_capacity(person["name"], week, today)
    tasks = [
        t for t in _tasks(today)
        if t.get("assignee") == person["name"]
        and t["status"] in OPEN_STATUSES
        and week_of(t["due_date"]) == week
    ]
    return {
        "name": person["name"],
        "week": week,
        "committed_hours": hours,
        "capacity_hours": capacity,
        "load_pct": round(hours / capacity, 3) if capacity else 0.0,
        "overload_streak": overload_streak(person["name"], week, today),
        "tasks": [
            {"title": t["title"], "est_hours": t["est_hours"],
             "due_date": t["due_date"], "status": t["status"]}
            for t in sorted(tasks, key=lambda t: t["due_date"])
        ],
    }


def list_open_tasks(status: str | None = None, due_before: str | None = None,
                     today: date | None = None) -> list[dict]:
    tasks = _tasks(today)
    if status:
        tasks = [t for t in tasks if t["status"] == status]
    else:
        tasks = [t for t in tasks if t["status"] in OPEN_STATUSES]
    if due_before:
        tasks = [t for t in tasks if t["due_date"] < due_before]
    return sorted(
        [
            {"id": t["id"], "title": t["title"], "est_hours": t["est_hours"],
             "due_date": t["due_date"], "status": t["status"],
             "assignee": t.get("assignee")}
            for t in tasks
        ],
        key=lambda t: t["due_date"],
    )


def get_capacity_forecast(weeks: int = 4, today: date | None = None) -> list[dict]:
    """Committed hours vs capacity for everyone, for the next N weeks.

    NOT a prediction -- it only counts work already in the fixture.
    """
    today = today or date.today()
    out = []
    for week in next_n_weeks(weeks, today):
        for person in get_team_roster(today):
            hours = assigned_hours(person["name"], week, today)
            capacity = effective_capacity(person["name"], week, today)
            out.append({
                "person": person["name"],
                "week": week,
                "committed_hours": hours,
                "capacity_hours": capacity,
                "load_pct": round(hours / capacity, 3) if capacity else 0.0,
            })
    return out


def build_snapshot(today: date | None = None, forecast_weeks: int = 3) -> dict:
    """Everything hr_manager_agent needs about the team, computed once and
    injected directly into its prompt (crews/hr/tasks.py) -- mirrors how
    crews/document injects knowledge/documents/*.json straight into its
    specialists' prompts instead of making them call read tools for it.
    """
    today = today or date.today()
    this_week = week_of(today)
    roster = get_team_roster(today)
    return {
        "today": today.isoformat(),
        "current_week": this_week,
        "team": [
            {
                "role": person["role"],
                "skills": person["skills"],
                "timezone": person["timezone"],
                "contact_handle": person["contact_handle"],
                **get_person_workload(person["name"], this_week, today),
            }
            for person in roster
        ],
        "capacity_forecast": get_capacity_forecast(forecast_weeks, today),
        "unassigned_tasks": list_open_tasks(status="unassigned", today=today),
    }
