"""
test_hr_roster.py
Tests for crews/hr's roster (JSON-fixture-backed reads) and safety rules.
No LLM, no API key, no network. Replaces test_hr_ledger.py now that the
SQLite ledger is gone (see crews/hr/roster.py and crews/hr/README.md):
each test builds its own tiny team fixture and monkeypatches
crews.hr.roster.load_team_roster to return it, instead of seeding a
throwaway database.

Every branch of check_assignment_safety has a case here, and the thresholds
are tested at their boundaries — off-by-one at 85% or 100% is the most likely
bug, and it's the one that makes a live demo behave differently to what you
promised thirty seconds earlier.
"""

from datetime import date, timedelta

import pytest

from crews.hr import roster, safety

THIS_MONDAY = date.today() - timedelta(days=date.today().weekday())
NEXT_MONDAY = THIS_MONDAY + timedelta(weeks=1)


def d(offset_from_next_monday: int) -> str:
    """A date in NEXT week — keeps tests clear of the current week's own
    boundary edge cases."""
    return (NEXT_MONDAY + timedelta(days=offset_from_next_monday)).isoformat()


def _offset_from_this_monday(iso_date: str) -> int:
    """roster.py resolves due_offset_days/leave offsets relative to THIS
    Monday, so fixtures built with d() (relative to NEXT Monday) need
    converting before they go in a task/leave entry."""
    return (date.fromisoformat(iso_date) - THIS_MONDAY).days


def _base_people():
    return [
        {"name": "Priya", "role": "Engineer", "skills": "backend,python",
         "weekly_capacity_hrs": 40, "timezone": "Asia/Singapore",
         "contact_handle": "", "overloaded_streak_weeks": 0, "leave": []},
        {"name": "Rahul", "role": "Engineer", "skills": "backend,onboarding",
         "weekly_capacity_hrs": 40, "timezone": "Asia/Singapore",
         "contact_handle": "", "overloaded_streak_weeks": 0, "leave": []},
        {"name": "Amara", "role": "Ops", "skills": "ops,finance",
         "weekly_capacity_hrs": 20, "timezone": "Asia/Singapore",
         "contact_handle": "", "overloaded_streak_weeks": 0, "leave": []},
    ]


@pytest.fixture
def team(monkeypatch):
    """A fresh, empty-of-tasks fixture for every test — mutate it with
    give()/set_leave()/set_streak() below, mirroring how the old
    ledger-backed tests built up a throwaway database per test."""
    state = {"people": _base_people(), "tasks": []}
    monkeypatch.setattr(roster, "load_team_roster", lambda: state)
    return state


def give(team, name, hours, due):
    """Add a task for `name`, due on ISO date `due`."""
    team["tasks"].append({
        "title": f"task {hours}h", "assignee": name, "est_hours": hours,
        "due_offset_days": _offset_from_this_monday(due),
        "status": "in_progress",
    })


def set_leave(team, name, start, end, note="trip"):
    for p in team["people"]:
        if p["name"] == name:
            p["leave"].append({
                "start_offset_days": _offset_from_this_monday(start),
                "end_offset_days": _offset_from_this_monday(end),
                "note": note,
            })


def set_streak(team, name, weeks):
    for p in team["people"]:
        if p["name"] == name:
            p["overloaded_streak_weeks"] = weeks


# ==========================================================================
# roster reads
# ==========================================================================

def test_roster_lists_everyone(team):
    assert [p["name"] for p in roster.get_team_roster()] == ["Amara", "Priya", "Rahul"]


def test_workload_counts_only_the_right_week(team):
    give(team, "Priya", 10, d(2))                  # next week
    give(team, "Priya", 30, d(9))                  # the week after
    w = roster.get_person_workload("Priya", roster.week_of(d(2)))
    assert w["committed_hours"] == 10              # not 40


def test_unknown_person_raises_with_a_useful_message(team):
    with pytest.raises(roster.RosterError) as e:
        roster.get_person_workload("Pria")
    assert "Priya" in str(e.value)                 # suggests the real names


def test_leave_reduces_effective_capacity(team):
    set_leave(team, "Amara", d(0), d(1))
    # 20h week, 2 of 5 working days off -> 12h
    assert roster.effective_capacity("Amara", roster.week_of(d(0))) == 12.0


# ==========================================================================
# safety — one test per branch
# ==========================================================================

def test_ok_when_well_under_capacity(team):
    assert safety.check_assignment_safety("Priya", 10, d(2)).verdict == "OK"


def test_block_when_over_capacity(team):
    give(team, "Priya", 35, d(2))
    v = safety.check_assignment_safety("Priya", 10, d(2))      # 45/40 = 112%
    assert v.verdict == "BLOCK"
    assert "112%" in v.reason


def test_warn_inside_the_warning_band(team):
    give(team, "Priya", 30, d(2))
    v = safety.check_assignment_safety("Priya", 5, d(2))       # 35/40 = 87.5%
    assert v.verdict == "WARN"


def test_block_when_on_leave(team):
    set_leave(team, "Rahul", d(2), d(3))
    v = safety.check_assignment_safety("Rahul", 2, d(2))
    assert v.verdict == "BLOCK" and "leave" in v.reason


def test_block_on_third_consecutive_overloaded_week(team):
    set_streak(team, "Priya", 2)
    give(team, "Priya", 30, d(2))
    v = safety.check_assignment_safety("Priya", 5, d(2))       # 87.5%: would be WARN alone
    assert v.verdict == "BLOCK"
    assert "weeks running" in v.reason


def test_warn_on_weekend_deadline(team):
    v = safety.check_assignment_safety("Priya", 4, d(5))       # Saturday
    assert v.verdict == "WARN" and "weekend" in v.reason


def test_unknown_person_blocks(team):
    assert safety.check_assignment_safety("Nobody", 4, d(2)).verdict == "BLOCK"


def test_bad_date_blocks(team):
    assert safety.check_assignment_safety("Priya", 4, "next tuesday").verdict == "BLOCK"


# ---- boundaries ----------------------------------------------------------

@pytest.mark.parametrize("committed, new, expected", [
    (33, 1, "OK"),      # 85.0% exactly -> WARN band starts here
    (30, 4, "OK"),      # 85.0%? no: 34/40 = 85.0
    (34, 6, "OK"),      # 100% exactly -> not over, so not BLOCK
])
def test_capacity_boundaries(team, committed, new, expected):
    give(team, "Priya", committed, d(2))
    v = safety.check_assignment_safety("Priya", new, d(2))
    load = (committed + new) / 40
    if load > 1.0:
        assert v.verdict == "BLOCK"
    elif load >= 0.85:
        assert v.verdict == "WARN"
    else:
        assert v.verdict == "OK"


# ==========================================================================
# alternatives
# ==========================================================================

def test_alternatives_exclude_the_blocked_person_and_respect_skills(team):
    give(team, "Priya", 38, d(2))
    options = safety.suggest_alternatives(6, d(2), exclude="Priya", required_skill="backend")
    names = [o["person"] for o in options]
    assert "Priya" not in names
    assert "Rahul" in names
    assert "Amara" not in names        # no backend skill


# ==========================================================================
# the checked-in demo fixture itself
# ==========================================================================

def test_checked_in_fixture_matches_its_own_schema():
    """knowledge/hr/team_roster.json is a fixture, not conversational input —
    a shape mismatch here is a repo bug callers can't fix by rephrasing.
    Sanity-checks it loads and resolves without the monkeypatched fixture
    above shadowing it."""
    people = roster.get_team_roster()
    assert any(p["name"] == "Priya Menon" for p in people)
    snapshot = roster.build_snapshot()
    assert snapshot["team"]
    assert "capacity_forecast" in snapshot
