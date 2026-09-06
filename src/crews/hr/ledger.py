"""
crews/hr/ledger.py
The eight ledger functions — four reads, four writes.

Plain Python returning plain dicts. Every one of these is unit-testable with
no API key and no model. The CrewAI tool wrappers in tools/ are thin shells
around these.

Ported from plan/workload_manager/ledger.py with no logic changes — only the
import (`from db import ...` -> `from crews.hr.db import ...`).
"""

from datetime import date, timedelta

from crews.hr.db import (
    connect,
    week_of,
    monday_of,
    next_n_weeks,
    previous_week,
    is_out_of_hours,
)

OPEN_STATUSES = ("unassigned", "in_progress")


class LedgerError(Exception):
    """Raised for bad input. Callers turn this into a message for the model,
    never into a crash."""


# ==========================================================================
# internal helpers
# ==========================================================================

def get_person(name_or_id) -> dict | None:
    """Look up by id, or by name case-insensitively. Returns None if absent."""
    with connect() as conn:
        if isinstance(name_or_id, int):
            row = conn.execute(
                "SELECT * FROM people WHERE id = ?", (name_or_id,)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM people WHERE lower(name) = lower(?)",
                (str(name_or_id).strip(),),
            ).fetchone()
    return dict(row) if row else None


def assigned_hours(person_id: int, week: str) -> float:
    """Committed hours for one person in one ISO week, from open tasks.

    Single source of truth for 'how loaded is this person'. The forecast and
    the safety check both call this, so they cannot drift apart.
    """
    with connect() as conn:
        rows = conn.execute(
            f"""SELECT est_hours, due_date FROM tasks
                WHERE assignee_id = ?
                  AND status IN ({','.join('?' * len(OPEN_STATUSES))})""",
            (person_id, *OPEN_STATUSES),
        ).fetchall()
    return round(sum(r["est_hours"] for r in rows if week_of(r["due_date"]) == week), 2)


def effective_capacity(person_id: int, week: str) -> float:
    """Weekly capacity, reduced pro-rata for any logged leave in that week."""
    person = get_person(person_id)
    capacity = person["weekly_capacity_hrs"]
    monday = monday_of(week)
    working_days = [monday + timedelta(days=i) for i in range(5)]
    off = sum(1 for d in working_days if on_leave(person_id, d.isoformat()))
    if off == 0:
        return capacity
    return round(capacity * (5 - off) / 5, 2)


def on_leave(person_id: int, day: str) -> bool:
    with connect() as conn:
        row = conn.execute(
            """SELECT 1 FROM wellbeing_events
               WHERE person_id = ? AND type IN ('leave', 'sick')
                 AND start_date <= ? AND end_date >= ?""",
            (person_id, day, day),
        ).fetchone()
    return row is not None


def overload_streak(person_id: int, week: str) -> int:
    """How many consecutive weeks BEFORE `week` this person was overloaded."""
    streak, cursor = 0, previous_week(week)
    with connect() as conn:
        while True:
            row = conn.execute(
                "SELECT overload_flag FROM workload_log WHERE person_id = ? AND week = ?",
                (person_id, cursor),
            ).fetchone()
            if row and row["overload_flag"]:
                streak += 1
                cursor = previous_week(cursor)
            else:
                return streak


def recompute_workload(person_id: int, week: str, warn_threshold: float = 0.85) -> None:
    """Refresh the workload_log row after any write. Call this from every
    function that changes an assignment or a status."""
    hours = assigned_hours(person_id, week)
    capacity = effective_capacity(person_id, week)
    flag = 1 if capacity and hours / capacity >= warn_threshold else 0
    with connect() as conn:
        conn.execute(
            """INSERT INTO workload_log (person_id, week, assigned_hours, overload_flag)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(person_id, week) DO UPDATE SET
                   assigned_hours = excluded.assigned_hours,
                   overload_flag  = excluded.overload_flag""",
            (person_id, week, hours, flag),
        )


# ==========================================================================
# READ functions — no side effects
# ==========================================================================

def get_team_roster() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM people ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def get_person_workload(name: str, week: str | None = None) -> dict:
    person = get_person(name)
    if not person:
        raise LedgerError(
            f"No one named '{name}' is in the ledger. "
            f"The team is: {', '.join(p['name'] for p in get_team_roster())}."
        )
    week = week or week_of(date.today())
    hours = assigned_hours(person["id"], week)
    capacity = effective_capacity(person["id"], week)

    with connect() as conn:
        rows = conn.execute(
            f"""SELECT id, title, est_hours, due_date, status FROM tasks
                WHERE assignee_id = ? AND status IN ({','.join('?' * len(OPEN_STATUSES))})
                ORDER BY due_date""",
            (person["id"], *OPEN_STATUSES),
        ).fetchall()

    return {
        "name": person["name"],
        "week": week,
        "committed_hours": hours,
        "capacity_hours": capacity,
        "load_pct": round(hours / capacity, 3) if capacity else 0.0,
        "overload_streak": overload_streak(person["id"], week),
        "tasks": [dict(r) for r in rows if week_of(r["due_date"]) == week],
    }


def list_open_tasks(status: str | None = None, due_before: str | None = None) -> list[dict]:
    sql = "SELECT t.*, p.name AS assignee FROM tasks t LEFT JOIN people p ON p.id = t.assignee_id WHERE 1=1"
    params: list = []
    if status:
        sql += " AND t.status = ?"
        params.append(status)
    else:
        sql += f" AND t.status IN ({','.join('?' * len(OPEN_STATUSES))})"
        params.extend(OPEN_STATUSES)
    if due_before:
        sql += " AND t.due_date < ?"
        params.append(due_before)
    sql += " ORDER BY t.due_date"
    with connect() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_capacity_forecast(weeks: int = 4) -> list[dict]:
    """Committed hours vs capacity for everyone, for the next N weeks.

    NOT a prediction — it only counts work already in the ledger.
    """
    out = []
    for week in next_n_weeks(weeks):
        for person in get_team_roster():
            hours = assigned_hours(person["id"], week)
            capacity = effective_capacity(person["id"], week)
            out.append({
                "person": person["name"],
                "week": week,
                "committed_hours": hours,
                "capacity_hours": capacity,
                "load_pct": round(hours / capacity, 3) if capacity else 0.0,
            })
    return out


# ==========================================================================
# WRITE functions — validate hard, return a quotable confirmation
# ==========================================================================

def create_task(title: str, est_hours: float, due_date: str,
                description: str = "", priority: str = "normal") -> dict:
    if not title or not title.strip():
        raise LedgerError("A task needs a title.")
    if est_hours <= 0 or est_hours > 40:
        raise LedgerError(
            f"{est_hours}h is not a plausible single task. Split it into smaller pieces."
        )
    try:
        due = date.fromisoformat(due_date)
    except ValueError:
        raise LedgerError(f"'{due_date}' is not a valid date. Use YYYY-MM-DD.")
    if due < date.today():
        raise LedgerError(f"{due_date} is in the past. Did you mean a later date?")

    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (title, description, est_hours, due_date, priority) "
            "VALUES (?, ?, ?, ?, ?)",
            (title.strip(), description, est_hours, due_date, priority),
        )
        task_id = cur.lastrowid
    return {"task_id": task_id, "title": title.strip(), "est_hours": est_hours,
            "due_date": due_date, "status": "unassigned",
            "confirmation": f"Created '{title.strip()}' ({est_hours}h, due {due_date}), unassigned."}


def assign_task(task_id: int, person: str, safety_verdict: str | None = None) -> dict:
    """Place a task on a person.

    PRECONDITION: safety_verdict must be the verdict check_assignment_safety
    returned for this exact pair. Without it this refuses — the guardrail is
    enforced here, in Python, not in the prompt.
    """
    if safety_verdict is None:
        raise LedgerError(
            "check_assignment_safety must be called for this person and task "
            "before assign_task. Call it now and pass its verdict."
        )
    if safety_verdict.upper() == "BLOCK":
        raise LedgerError(
            "This assignment was BLOCKED by the safety check and cannot be made. "
            "Propose an alternative person or a later date."
        )

    who = get_person(person)
    if not who:
        raise LedgerError(f"No one named '{person}' is in the ledger.")

    with connect() as conn:
        task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not task:
            raise LedgerError(f"No task with id {task_id}.")
        conn.execute(
            "UPDATE tasks SET assignee_id = ?, status = 'in_progress' WHERE id = ?",
            (who["id"], task_id),
        )

    week = week_of(task["due_date"])
    recompute_workload(who["id"], week)
    after = get_person_workload(who["name"], week)

    return {
        "task_id": task_id,
        "assignee": who["name"],
        "week": week,
        "load_pct": after["load_pct"],
        "confirmation": (
            f"Assigned '{task['title']}' ({task['est_hours']}h, due {task['due_date']}) "
            f"to {who['name']}. They're now at {after['load_pct']:.0%} for {week}."
        ),
    }


def update_task_status(task_id: int, status: str) -> dict:
    valid = ("unassigned", "in_progress", "done", "cancelled")
    if status not in valid:
        raise LedgerError(f"'{status}' is not a status. Use one of: {', '.join(valid)}.")
    with connect() as conn:
        task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not task:
            raise LedgerError(f"No task with id {task_id}.")
        conn.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))

    if task["assignee_id"]:
        recompute_workload(task["assignee_id"], week_of(task["due_date"]))
    return {"task_id": task_id, "status": status,
            "confirmation": f"'{task['title']}' is now {status}."}


def log_wellbeing_event(person: str, type: str, note: str = "",
                        start_date: str | None = None,
                        end_date: str | None = None) -> dict:
    valid = ("leave", "sick", "overloaded", "flagged", "override_approved")
    if type not in valid:
        raise LedgerError(f"'{type}' is not an event type. Use one of: {', '.join(valid)}.")
    who = get_person(person)
    if not who:
        raise LedgerError(f"No one named '{person}' is in the ledger.")
    if type in ("leave", "sick") and not (start_date and end_date):
        raise LedgerError("Leave and sick events need both start_date and end_date.")

    with connect() as conn:
        conn.execute(
            "INSERT INTO wellbeing_events (person_id, type, note, start_date, end_date) "
            "VALUES (?, ?, ?, ?, ?)",
            (who["id"], type, note, start_date, end_date),
        )
    span = f" from {start_date} to {end_date}" if start_date else ""
    return {"person": who["name"], "type": type,
            "confirmation": f"Logged '{type}' for {who['name']}{span}."}
