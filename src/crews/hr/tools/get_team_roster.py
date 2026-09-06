"""
crews/hr/tools/get_team_roster.py
CrewAI tool wrapper — read.

Referenced from crews/hr/agents.py as one of hr_manager_agent's tools.
Ported from plan/workload_manager/tools/get_team_roster.py — only the import
of the underlying ledger function changed.
"""

import json

from crewai.tools import BaseTool
from pydantic import BaseModel

from crews.hr.ledger import get_team_roster as _get_team_roster


class RosterInput(BaseModel):
    """No arguments. The roster is the whole team, always."""


class GetTeamRoster(BaseTool):
    name: str = "get_team_roster"

    description: str = (
        "List everyone on the team with their role, skills, weekly capacity in "
        "hours, timezone and contact handle. Takes no arguments. "
        "Call this FIRST whenever the founder names a person you have not seen "
        "yet, or asks who could do a piece of work — names must come from this "
        "roster and never from your own guess. Skills are a comma-separated "
        "string; match against it before proposing anybody for a task."
    )
    args_schema: type[BaseModel] = RosterInput

    def _run(self) -> str:
        try:
            return json.dumps(_get_team_roster(), indent=2, default=str)
        except Exception as exc:
            return f"ERROR: {exc}"


get_team_roster = GetTeamRoster()
tool = get_team_roster
