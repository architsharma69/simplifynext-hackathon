"""
crews/hr/safety.py
The guardrail.

Ordinary Python with fixed rules — not an instruction to the AI, so it can't
be argued out of a refusal. No model call, no randomness: the same inputs
always give the same verdict.

Thresholds are POLICY, not truth. In a real deployment the founder sets them.

Ported from plan/workload_manager/safety.py with the same rules and
thresholds — only the data source changed: reads now come from
crews.hr.roster (backed by the static knowledge/hr/team_roster.json
fixture) instead of a SQLite ledger, and people are looked up by name
throughout rather than by a database id.
"""

from dataclasses import dataclass, asdict
from datetime import date

from crews.hr.roster import (
    week_of,
    is_out_of_hours,
    get_person,
    assigned_hours,
    effective_capacity,
    on_leave,
    overload_streak,
    get_team_roster,
)

# ---- policy --------------------------------------------------------------
CAPACITY_WARN = 0.85          # >= this is a WARN
CAPACITY_BLOCK = 1.00         # >  this is a BLOCK
OVERLOAD_STREAK_LIMIT = 3     # this many consecutive overloaded weeks is a BLOCK


@dataclass
class Verdict:
    verdict: str       # "OK" | "WARN" | "BLOCK"
    reason: str        # human-readable; the agent quotes this to the founder
    load_pct: float

    def dict(self) -> dict:
        return asdict(self)

    def __str__(self) -> str:
        return f"{self.verdict}: {self.reason}"


def check_assignment_safety(person: str, est_hours: float, due_date: str) -> Verdict:
    """Is it safe to put `est_hours` of work on `person`, due `due_date`?

    Rules are checked MOST SEVERE FIRST and the function returns on the first
    match, so leave beats capacity and capacity beats the warning band.
    Do not reorder these without thinking about that.
    """
    who = get_person(person)
    if not who:
        names = ", ".join(p["name"] for p in get_team_roster())
        return Verdict("BLOCK", f"No one named '{person}' is in the roster. The team is: {names}.", 0.0)

    try:
        due = date.fromisoformat(due_date)
    except ValueError:
        return Verdict("BLOCK", f"'{due_date}' is not a valid date. Use YYYY-MM-DD.", 0.0)

    if est_hours <= 0:
        return Verdict("BLOCK", f"{est_hours}h is not a valid estimate.", 0.0)

    week = week_of(due)

    # 1 — leave beats everything
    if on_leave(who["name"], due_date):
        return Verdict("BLOCK", f"{who['name']} is on logged leave on {due_date}.", 0.0)

    capacity = effective_capacity(who["name"], week)
    if capacity <= 0:
        return Verdict("BLOCK", f"{who['name']} has no working capacity in {week}.", 0.0)

    committed = assigned_hours(who["name"], week)
    load = (committed + est_hours) / capacity

    # 2 — hard capacity ceiling
    if load > CAPACITY_BLOCK:
        return Verdict(
            "BLOCK",
            f"{who['name']} would be at {load:.0%} in {week} — "
            f"{committed + est_hours:.0f}h against a {capacity:.0f}h week.",
            round(load, 3),
        )

    # 3 — sustained overload, even when this week alone is survivable
    streak = overload_streak(who["name"], week)
    if streak >= OVERLOAD_STREAK_LIMIT - 1 and load >= CAPACITY_WARN:
        return Verdict(
            "BLOCK",
            f"{who['name']} has been above {CAPACITY_WARN:.0%} for {streak} weeks running. "
            f"This would make it {streak + 1}.",
            round(load, 3),
        )

    # 4 — warning band
    if load >= CAPACITY_WARN:
        return Verdict(
            "WARN",
            f"{who['name']} would be at {load:.0%} in {week} "
            f"({committed + est_hours:.0f}h of {capacity:.0f}h).",
            round(load, 3),
        )

    # 5 — soft signal
    if is_out_of_hours(due):
        return Verdict(
            "WARN",
            f"The deadline {due_date} falls on a weekend.",
            round(load, 3),
        )

    return Verdict(
        "OK",
        f"{who['name']} would be at {load:.0%} in {week} "
        f"({committed + est_hours:.0f}h of {capacity:.0f}h).",
        round(load, 3),
    )


def suggest_alternatives(est_hours: float, due_date: str, exclude: str = "",
                         required_skill: str = "") -> list[dict]:
    """Who else could take this? Only ever returns people who pass the check.

    Pass required_skill to filter to people who can actually do the work.
    """
    week = week_of(due_date)
    options = []
    for person in get_team_roster():
        if exclude and person["name"].lower() == exclude.lower():
            continue
        if required_skill and required_skill.lower() not in person["skills"].lower():
            continue
        v = check_assignment_safety(person["name"], est_hours, due_date)
        if v.verdict == "OK":
            options.append({
                "person": person["name"],
                "reason": f"would be at {v.load_pct:.0%} in {week}",
                "load_pct": v.load_pct,
            })
    return sorted(options, key=lambda o: o["load_pct"])[:3]
