"""
crews/hr/tools/list_open_tasks.py
CrewAI tool wrapper — read.

Referenced from crews/hr/agents.py as one of hr_manager_agent's tools.
Ported from plan/workload_manager/tools/list_open_tasks.py — only the import
of the underlying ledger function changed.
"""

import json
from typing import Optional

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crews.hr.ledger import list_open_tasks as _list_open_tasks


class OpenTasksInput(BaseModel):
    status: Optional[str] = Field(
        None,
        description="Filter to one status: unassigned, in_progress, done or "
                    "cancelled. Leave empty for all open work, which means "
                    "unassigned and in_progress together.",
    )
    due_before: Optional[str] = Field(
        None,
        description="Only tasks due strictly before this date, as YYYY-MM-DD.",
    )


class ListOpenTasks(BaseTool):
    name: str = "list_open_tasks"

    description: str = (
        "List tasks in the ledger with their id, title, estimated hours, due date, "
        "status, priority and assignee (null when nobody holds it). "
        "Use this to find the task_id you need for assign_task or "
        "update_task_status — never invent an id. Also use it to answer 'what is "
        "unassigned' or 'what is due this week'. Default is all open work; pass "
        "status='unassigned' for work that still needs an owner."
    )
    args_schema: type[BaseModel] = OpenTasksInput

    def _run(self, status: Optional[str] = None, due_before: Optional[str] = None) -> str:
        try:
            return json.dumps(_list_open_tasks(status, due_before), indent=2, default=str)
        except Exception as exc:
            return f"ERROR: {exc}"


list_open_tasks = ListOpenTasks()
tool = list_open_tasks
