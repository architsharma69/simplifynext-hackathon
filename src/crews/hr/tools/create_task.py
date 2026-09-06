"""
crews/hr/tools/create_task.py
CrewAI tool wrapper — write, but stateless.

There is no ledger any more (see crews/hr/roster.py and
crews/hr/README.md): this validates a new piece of work exactly the way
the old SQLite-backed version did — sane estimate, sane date — and returns
the same shape of confirmation, but nothing is stored. The founder-facing
behavior is unchanged; only persistence is gone.

Referenced from crews/hr/agents.py as one of hr_manager_agent's tools.
"""

from datetime import date

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crews.hr.roster import RosterError


class CreateTaskInput(BaseModel):
    title: str = Field(..., description="Short name for the work, as the founder said it.")
    est_hours: float = Field(
        ...,
        description="Estimated hours. Must be between 0 and 40 — anything larger "
                    "is not one task, so split it and create several.",
    )
    due_date: str = Field(
        ..., description="Due date as YYYY-MM-DD. Must not be in the past."
    )


class CreateTask(BaseTool):
    name: str = "create_task"

    description: str = (
        "Validate a new piece of work — checks the estimate and due date are "
        "sane. It starts UNASSIGNED; this tool does not put it on anybody. "
        "Returns a confirmation you can quote back to the founder. "
        "If the founder asked you to give the work to a named person, call this "
        "first, then check_assignment_safety, then assign_task with the same "
        "title/hours/date. Do not guess the estimate or the date: if either is "
        "missing, ask the founder before creating anything."
    )
    args_schema: type[BaseModel] = CreateTaskInput

    def _run(self, title: str, est_hours: float, due_date: str) -> str:
        try:
            if not title or not title.strip():
                raise RosterError("A task needs a title.")
            if est_hours <= 0 or est_hours > 40:
                raise RosterError(
                    f"{est_hours}h is not a plausible single task. Split it into smaller pieces."
                )
            try:
                due = date.fromisoformat(due_date)
            except ValueError:
                raise RosterError(f"'{due_date}' is not a valid date. Use YYYY-MM-DD.")
            if due < date.today():
                raise RosterError(f"{due_date} is in the past. Did you mean a later date?")
            return f"'{title.strip()}' ({est_hours}h, due {due_date}) is unassigned and ready to place."
        except Exception as exc:
            return f"ERROR: {exc}"


create_task = CreateTask()
tool = create_task
