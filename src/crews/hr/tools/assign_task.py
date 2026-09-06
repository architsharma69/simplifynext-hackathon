"""
crews/hr/tools/assign_task.py
CrewAI tool wrapper — write, and the one the guardrail hangs off.

This still refuses without a safety verdict, and still refuses a BLOCK
verdict outright, exactly like the old SQLite-backed version — that
refusal is enforced in Python here, not just in the prompt, so it can't be
talked around. What changed is persistence: there is no ledger row behind
this any more (see crews/hr/roster.py and crews/hr/README.md), so this
confirms an assignment instead of recording one. The projected load_pct
in the confirmation is arithmetic over the current snapshot plus this one
hypothetical addition — it is not saved anywhere, so asking again a moment
later will not reflect it.

Referenced from crews/hr/agents.py as one of hr_manager_agent's tools.
"""

from typing import Optional

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crews.hr.roster import RosterError, get_person, get_person_workload, week_of
from crews.hr.safety import suggest_alternatives


class AssignTaskInput(BaseModel):
    title: str = Field(..., description="The task's title, exactly as given to create_task.")
    person: str = Field(
        ..., description="Full name of the person, exactly as it appears in the roster."
    )
    est_hours: float = Field(..., description="Estimated hours for this task.")
    due_date: str = Field(..., description="Due date as YYYY-MM-DD.")
    safety_verdict: Optional[str] = Field(
        None,
        description="The verdict word — OK, WARN or BLOCK — that "
                    "check_assignment_safety returned for THIS person and THIS "
                    "task. Copy it, do not decide it yourself.",
    )


class AssignTask(BaseTool):
    name: str = "assign_task"

    description: str = (
        "Confirm putting a task on a person. "
        "PRECONDITION: call check_assignment_safety for this exact person, hours "
        "and due date first, and pass its verdict here. Without a verdict this "
        "refuses, and a BLOCK verdict refuses too. "
        "On OK: assign. "
        "On WARN: do not call this until the founder has confirmed in words; then "
        "call it with the WARN verdict. "
        "On BLOCK: do not call this at all — report the reason and offer an "
        "alternative person or a later date. "
        "Returns a confirmation with the person's projected load for that week; "
        "quote that number back to the founder."
    )
    args_schema: type[BaseModel] = AssignTaskInput

    def _run(self, title: str, person: str, est_hours: float, due_date: str,
             safety_verdict: Optional[str] = None) -> str:
        try:
            if safety_verdict is None:
                raise RosterError(
                    "check_assignment_safety must be called for this person and task "
                    "before assign_task. Call it now and pass its verdict."
                )
            if safety_verdict.upper() == "BLOCK":
                raise RosterError(
                    "This assignment was BLOCKED by the safety check and cannot be made. "
                    "Propose an alternative person or a later date."
                )
            who = get_person(person)
            if not who:
                raise RosterError(f"No one named '{person}' is in the roster.")

            week = week_of(due_date)
            current = get_person_workload(who["name"], week)
            capacity = current["capacity_hours"]
            projected_pct = (
                round((current["committed_hours"] + est_hours) / capacity, 3)
                if capacity else 0.0
            )
            return (
                f"Assigned '{title}' ({est_hours}h, due {due_date}) to {who['name']}. "
                f"They're now at {projected_pct:.0%} for {week}."
            )
        except RosterError as exc:
            return f"ERROR: {exc}{self._alternatives_for(est_hours, due_date, person)}"
        except Exception as exc:
            return f"ERROR: {exc}"

    @staticmethod
    def _alternatives_for(est_hours: float, due_date: str, person: str) -> str:
        """Best-effort extra help on a refusal. Never raises — a failure here
        must not turn a clean refusal into a crash."""
        try:
            options = suggest_alternatives(est_hours, due_date, exclude=person)
            if not options:
                return " No one else is clear for that week either — propose a later date."
            names = "; ".join(f"{o['person']} ({o['reason']})" for o in options)
            return f" People who would pass instead: {names}."
        except Exception:
            return ""


assign_task = AssignTask()
tool = assign_task
