"""
crews/hr/tools/assign_task.py
CrewAI tool wrapper — write, and the one the guardrail hangs off.

ledger.assign_task refuses without a safety verdict, in Python. This wrapper
does not soften that. It only makes the refusal more useful: when the ledger
says no, it attaches the people who WOULD pass, so the agent has something to
offer instead of an apology.

Referenced from crews/hr/agents.py as one of hr_manager_agent's tools.
Ported from plan/workload_manager/tools/assign_task.py — only the imports of
the underlying ledger/safety functions changed.
"""

import json
from typing import Optional

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crews.hr.ledger import LedgerError, assign_task as _assign_task, list_open_tasks
from crews.hr.safety import suggest_alternatives


class AssignTaskInput(BaseModel):
    task_id: int = Field(
        ...,
        description="The task's id from list_open_tasks or create_task. Never guessed.",
    )
    person: str = Field(
        ..., description="Full name of the person, exactly as it appears in the roster."
    )
    safety_verdict: Optional[str] = Field(
        None,
        description="The verdict word — OK, WARN or BLOCK — that "
                    "check_assignment_safety returned for THIS person and THIS "
                    "task. Copy it, do not decide it yourself.",
    )


class AssignTask(BaseTool):
    name: str = "assign_task"

    description: str = (
        "Put an existing task on a person and mark it in progress. "
        "PRECONDITION: call check_assignment_safety for this exact person, hours "
        "and due date first, and pass its verdict here. Without a verdict this "
        "refuses, and a BLOCK verdict refuses too. "
        "On OK: assign. "
        "On WARN: do not call this until the founder has confirmed in words; then "
        "call it with the WARN verdict. "
        "On BLOCK: do not call this at all — report the reason and offer an "
        "alternative person or a later date. "
        "Returns a confirmation with the person's new load for that week; quote "
        "that number back to the founder."
    )
    args_schema: type[BaseModel] = AssignTaskInput

    def _run(self, task_id: int, person: str,
             safety_verdict: Optional[str] = None) -> str:
        try:
            result = _assign_task(task_id, person, safety_verdict)
            return json.dumps(result, indent=2, default=str)
        except LedgerError as exc:
            return f"ERROR: {exc}{self._alternatives_for(task_id, person)}"
        except Exception as exc:
            return f"ERROR: {exc}"

    @staticmethod
    def _alternatives_for(task_id: int, person: str) -> str:
        """Best-effort extra help on a refusal. Never raises — a failure here
        must not turn a clean refusal into a crash."""
        try:
            task = next(
                (t for t in list_open_tasks() if t["id"] == task_id), None
            )
            if not task:
                return ""
            options = suggest_alternatives(
                task["est_hours"], task["due_date"], exclude=person
            )
            if not options:
                return " No one else is clear for that week either — propose a later date."
            names = "; ".join(f"{o['person']} ({o['reason']})" for o in options)
            return f" People who would pass instead: {names}."
        except Exception:
            return ""


assign_task = AssignTask()
tool = assign_task
