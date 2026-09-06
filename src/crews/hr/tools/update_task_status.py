"""
crews/hr/tools/update_task_status.py
CrewAI tool wrapper — write, but stateless (see crews/hr/roster.py and
crews/hr/README.md). There is no persisted task for this to actually
update any more, so it validates the status word and confirms the change
without touching anything — closing a task no longer frees hours in a
later check_assignment_safety call, since nothing here is remembered
between requests.

Referenced from crews/hr/agents.py as one of hr_manager_agent's tools.
"""

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crews.hr.roster import RosterError


class UpdateStatusInput(BaseModel):
    title: str = Field(..., description="The task's title, exactly as the founder gave it.")
    status: str = Field(
        ...,
        description="One of: unassigned, in_progress, done, cancelled.",
    )


class UpdateTaskStatus(BaseTool):
    name: str = "update_task_status"

    description: str = (
        "Confirm a task's status change. Use 'done' when the founder says work "
        "finished and 'cancelled' when it is dropped. "
        "Do not use this to reassign work; that is assign_task."
    )
    args_schema: type[BaseModel] = UpdateStatusInput

    def _run(self, title: str, status: str) -> str:
        try:
            valid = ("unassigned", "in_progress", "done", "cancelled")
            if status not in valid:
                raise RosterError(f"'{status}' is not a status. Use one of: {', '.join(valid)}.")
            return f"'{title}' is now {status}."
        except Exception as exc:
            return f"ERROR: {exc}"


update_task_status = UpdateTaskStatus()
tool = update_task_status
