"""
crews/hr/tools/check_assignment_safety.py
CrewAI tool wrapper — the pattern all ten follow.

Wrappers stay thin on purpose: the logic lives in safety.py / ledger.py where
it can be tested without a model. All this layer does is (a) describe the tool
to the LLM and (b) turn exceptions into text the agent can recover from.

Referenced from crews/hr/agents.py as one of hr_manager_agent's tools.
Ported from plan/workload_manager/tools/check_assignment_safety.py — only the
import of the underlying safety function changed.
"""

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crews.hr.safety import check_assignment_safety as _check


class SafetyInput(BaseModel):
    person: str = Field(
        ..., description="Full name of the person, exactly as it appears in the roster."
    )
    est_hours: float = Field(
        ..., description="Estimated hours of work for this task."
    )
    due_date: str = Field(
        ..., description="Due date as YYYY-MM-DD. Use the date the task is due, "
                         "not today's date."
    )


class CheckAssignmentSafety(BaseTool):
    name: str = "check_assignment_safety"

    # This string is a PROMPT. The model chooses this tool by reading it, and
    # decides what to do with the result by reading it. Tune here first when
    # the agent misbehaves.
    description: str = (
        "Check whether it is safe to assign work to a person before you assign it. "
        "You MUST call this before assign_task, every time, with no exceptions. "
        "Returns OK, WARN or BLOCK with a reason. "
        "OK: go ahead and call assign_task. "
        "WARN: do not assign yet — report the warning and its reason to the founder "
        "and ask them to confirm. "
        "BLOCK: do not assign, and do not look for a way around it. State the reason "
        "plainly and propose an alternative person or a later date."
    )
    args_schema: type[BaseModel] = SafetyInput

    def _run(self, person: str, est_hours: float, due_date: str) -> str:
        try:
            return str(_check(person, est_hours, due_date))
        except Exception as exc:
            # Return the error as text, never raise. The agent reads this and
            # recovers; a raised exception kills the run.
            return f"ERROR: {exc}"


# The scaffold may expect a module-level instance, a class, or a factory —
# exporting all three costs nothing and saves a debugging cycle.
check_assignment_safety = CheckAssignmentSafety()
tool = check_assignment_safety
