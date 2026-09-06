"""
crews/hr/tools/update_task_status.py
CrewAI tool wrapper — write.

Closing a task frees the hours it was holding, so this is also the tool that
makes an overloaded week survivable. Recomputing the workload log is handled
in ledger.update_task_status.

Referenced from crews/hr/agents.py as one of hr_manager_agent's tools.
Ported from plan/workload_manager/tools/update_task_status.py — only the
import of the underlying ledger function changed.
"""

import json

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crews.hr.ledger import update_task_status as _update_task_status


class UpdateStatusInput(BaseModel):
    task_id: int = Field(
        ..., description="The task's id from list_open_tasks. Never guessed."
    )
    status: str = Field(
        ...,
        description="One of: unassigned, in_progress, done, cancelled. "
                    "'unassigned' does not clear the assignee — it only changes "
                    "the status.",
    )


class UpdateTaskStatus(BaseTool):
    name: str = "update_task_status"

    description: str = (
        "Change a task's status. Use 'done' when the founder says work finished "
        "and 'cancelled' when it is dropped. "
        "Both of these release the hours the task was holding, so a person who "
        "was blocked before may be assignable afterwards — re-run "
        "check_assignment_safety rather than assuming either way. "
        "Do not use this to reassign work; that is assign_task."
    )
    args_schema: type[BaseModel] = UpdateStatusInput

    def _run(self, task_id: int, status: str) -> str:
        try:
            return json.dumps(_update_task_status(task_id, status), indent=2, default=str)
        except Exception as exc:
            return f"ERROR: {exc}"


update_task_status = UpdateTaskStatus()
tool = update_task_status
