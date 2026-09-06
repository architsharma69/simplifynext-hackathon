"""
test_hr_ledger.py
Tests for crews/hr's ledger and safety rules. No LLM, no API key, no
network — ported verbatim from the standalone prototype's test_ledger.py,
only the imports changed (`import db` / `import ledger` / `import safety`
-> `from crews.hr import db, ledger, safety`).

Every branch of check_assignment_safety has a case here, and the thresholds
are tested at their boundaries — off-by-one at 85% or 100% is the most likely
bug, and it's the one that makes a live demo behave differently to what you
promised thirty seconds earlier.
"""

from datetime import date, timedelta

import pytest

from crews.hr import db, ledger, safety
from crews.hr.db import week_of


THIS_MONDAY = date.today() - timedelta(days=date.today().weekday())
NEXT_MONDAY = THIS_MONDAY + timedelta(weeks=1)


def d(offset_from_next_monday: int) -> str:
    """A date in NEXT week — keeps tests clear of the seeded current week."""
    return (NEXT_MONDAY + timedelta(days=offset_from_next_monday)).isoformat()


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Every test gets its own empty database (not the checked-in seeded one)."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db(reset=True)
    with db.connect() as conn:
        conn.executemany(
            "INSERT INTO people (name, role, skills, weekly_capacity_hrs) VALUES (?,?,?,?)",
            [("Priya", "Engineer", "backend,python", 40),
             ("Rahul", "Engineer", "backend,onboarding", 40),
             ("Amara", "Ops", "ops,finance", 20)],
        )
    yield


def person_id(name):
    return ledger.get_person(name)["id"]


def give(name, hours, due):
    """Helper: create a task and force it onto someone, bypassing the guard."""
    t = ledger.create_task(f"task {hours}h", hours, due)
    with db.connect() as conn:
        conn.execute("UPDATE tasks SET assignee_id = ?, status = 'in_progress' WHERE id = ?",
                     (person_id(name), t["task_id"]))
    ledger.recompute_workload(person_id(name), week_of(due))
    return t["task_id"]


# ==========================================================================
# ledger reads
# ==========================================================================

def test_roster_lists_everyone():
    assert [p["name"] for p in ledger.get_team_roster()] == ["Amara", "Priya", "Rahul"]


def test_workload_counts_only_the_right_week():
    give("Priya", 10, d(2))                       # next week
    give("Priya", 30, d(9))                       # the week after
    w = ledger.get_person_workload("Priya", week_of(d(2)))
    assert w["committed_hours"] == 10             # not 40


def test_unknown_person_raises_with_a_useful_message():
    with pytest.raises(ledger.LedgerError) as e:
        ledger.get_person_workload("Pria")
    assert "Priya" in str(e.value)                # suggests the real names


def test_leave_reduces_effective_capacity():
    ledger.log_wellbeing_event("Amara", "leave", "trip", d(0), d(1))
    # 20h week, 2 of 5 working days off -> 12h
    assert ledger.effective_capacity(person_id("Amara"), week_of(d(0))) == 12.0


# ==========================================================================
# safety — one test per branch
# ==========================================================================

def test_ok_when_well_under_capacity():
    assert safety.check_assignment_safety("Priya", 10, d(2)).verdict == "OK"


def test_block_when_over_capacity():
    give("Priya", 35, d(2))
    v = safety.check_assignment_safety("Priya", 10, d(2))       # 45/40 = 112%
    assert v.verdict == "BLOCK"
    assert "112%" in v.reason


def test_warn_inside_the_warning_band():
    give("Priya", 30, d(2))
    v = safety.check_assignment_safety("Priya", 5, d(2))        # 35/40 = 87.5%
    assert v.verdict == "WARN"


def test_block_when_on_leave():
    ledger.log_wellbeing_event("Rahul", "leave", "sick kid", d(2), d(3))
    v = safety.check_assignment_safety("Rahul", 2, d(2))
    assert v.verdict == "BLOCK" and "leave" in v.reason


def test_block_on_third_consecutive_overloaded_week():
    week = week_of(d(2))
    with db.connect() as conn:
        for wk in (db.previous_week(week), db.previous_week(db.previous_week(week))):
            conn.execute(
                "INSERT INTO workload_log (person_id, week, assigned_hours, overload_flag) "
                "VALUES (?, ?, 40, 1)", (person_id("Priya"), wk))
    give("Priya", 30, d(2))
    v = safety.check_assignment_safety("Priya", 5, d(2))        # 87.5%: would be WARN alone
    assert v.verdict == "BLOCK"
    assert "weeks running" in v.reason


def test_warn_on_weekend_deadline():
    v = safety.check_assignment_safety("Priya", 4, d(5))        # Saturday
    assert v.verdict == "WARN" and "weekend" in v.reason


def test_unknown_person_blocks():
    assert safety.check_assignment_safety("Nobody", 4, d(2)).verdict == "BLOCK"


def test_bad_date_blocks():
    assert safety.check_assignment_safety("Priya", 4, "next tuesday").verdict == "BLOCK"


# ---- boundaries ----------------------------------------------------------

@pytest.mark.parametrize("committed, new, expected", [
    (33, 1, "OK"),      # 85.0% exactly -> WARN band starts here
    (30, 4, "OK"),      # 85.0%? no: 34/40 = 85.0
    (34, 6, "OK"),      # 100% exactly -> not over, so not BLOCK
])
def test_capacity_boundaries(committed, new, expected):
    give("Priya", committed, d(2))
    v = safety.check_assignment_safety("Priya", new, d(2))
    load = (committed + new) / 40
    if load > 1.0:
        assert v.verdict == "BLOCK"
    elif load >= 0.85:
        assert v.verdict == "WARN"
    else:
        assert v.verdict == "OK"


# ==========================================================================
# writes
# ==========================================================================

def test_assign_refuses_without_a_verdict():
    t = ledger.create_task("something", 4, d(2))
    with pytest.raises(ledger.LedgerError) as e:
        ledger.assign_task(t["task_id"], "Priya")
    assert "check_assignment_safety" in str(e.value)


def test_assign_refuses_on_a_block_verdict():
    t = ledger.create_task("something", 4, d(2))
    with pytest.raises(ledger.LedgerError):
        ledger.assign_task(t["task_id"], "Priya", safety_verdict="BLOCK")


def test_assign_works_with_an_ok_verdict_and_updates_workload():
    t = ledger.create_task("something", 8, d(2))
    result = ledger.assign_task(t["task_id"], "Priya", safety_verdict="OK")
    assert result["assignee"] == "Priya"
    assert ledger.get_person_workload("Priya", week_of(d(2)))["committed_hours"] == 8


def test_completing_a_task_frees_capacity():
    tid = give("Priya", 20, d(2))
    ledger.update_task_status(tid, "done")
    assert ledger.get_person_workload("Priya", week_of(d(2)))["committed_hours"] == 0


def test_create_task_rejects_a_past_date():
    with pytest.raises(ledger.LedgerError):
        ledger.create_task("late", 4, (date.today() - timedelta(days=3)).isoformat())


def test_create_task_rejects_an_absurd_estimate():
    with pytest.raises(ledger.LedgerError):
        ledger.create_task("epic", 200, d(2))


# ==========================================================================
# alternatives
# ==========================================================================

def test_alternatives_exclude_the_blocked_person_and_respect_skills():
    give("Priya", 38, d(2))
    options = safety.suggest_alternatives(6, d(2), exclude="Priya", required_skill="backend")
    names = [o["person"] for o in options]
    assert "Priya" not in names
    assert "Rahul" in names
    assert "Amara" not in names        # no backend skill
