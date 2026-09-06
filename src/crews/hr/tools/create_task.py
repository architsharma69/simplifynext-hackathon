"""
crews/hr/tools/create_task.py
CrewAI tool wrapper — write.

Creating a task and assigning it are deliberately two separate tools. A task
can exist with nobody on it; that is a normal, safe state, and it means the
agent can capture work even when there is no safe home for it yet.

Referenced from crews/hr/agents.py as one of hr_manager_agent's tools.
Ported from plan/workload_manager/tools/create_task.py — only the import of
the underlying ledger function changed.
"""

import json

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crews.hr.ledger import create_task as _create_task


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
    description: str = Field("", description="Any detail the founder gave. Optional.")
    priority: str = Field(
        "normal", description="low, normal or high. Default normal."
    )


class CreateTask(BaseTool):
    name: str = "create_task"

    description: str = (
        "Add a new piece of work to the ledger. It starts UNASSIGNED — this tool "
        "does not put it on anybody. "
        "Returns the task_id, which you need for assign_task. "
        "If the founder asked you to give the work to a named person, call this "
        "first, then check_assignment_safety, then assign_task. "
        "Do not guess the estimate or the date: if either is missing, ask the "
        "founder before creating anything."
    )
    args_schema: type[BaseModel] = CreateTaskInput

    def _run(self, title: str, est_hours: float, due_date: str,
             description: str = "", priority: str = "normal") -> str:
        try:
            result = _create_task(title, est_hours, due_date, description, priority)
            return json.dumps(result, indent=2, default=str)
        except Exception as exc:
            return f"ERROR: {exc}"


create_task = CreateTask()
tool = create_task
