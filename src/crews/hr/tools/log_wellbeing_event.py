"""
crews/hr/tools/log_wellbeing_event.py
CrewAI tool wrapper — write, but stateless (see crews/hr/roster.py and
crews/hr/README.md). Confirms the event after checking the person is real
and the event is well-formed; it no longer reduces anyone's effective
capacity, since nothing persists between requests. Leave/sick days that
should count against capacity for the demo belong in
knowledge/hr/team_roster.json's per-person "leave" list instead.

Referenced from crews/hr/agents.py as one of hr_manager_agent's tools.
"""

from typing import Optional

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crews.hr.roster import RosterError, get_person, get_team_roster


class WellbeingInput(BaseModel):
    person: str = Field(
        ..., description="Full name of the person, exactly as it appears in the roster."
    )
    type: str = Field(
        ...,
        description="One of: leave, sick, overloaded, flagged, override_approved. "
                    "Use 'leave' for planned time off, 'sick' for unplanned, "
                    "'flagged' when you raise a concern, and 'override_approved' "
                    "only after the founder has explicitly confirmed a WARN.",
    )
    note: str = Field("", description="What the founder actually said. Optional.")
    start_date: Optional[str] = Field(
        None, description="YYYY-MM-DD. Required for leave and sick."
    )
    end_date: Optional[str] = Field(
        None,
        description="YYYY-MM-DD, inclusive. Required for leave and sick. "
                    "For a single day off, use the same date as start_date.",
    )


class LogWellbeingEvent(BaseTool):
    name: str = "log_wellbeing_event"

    description: str = (
        "Confirm recording leave, sickness, an overload concern, or an approved "
        "override against a person. "
        "Log 'flagged' when you tell the founder somebody is carrying too much, so "
        "the pattern is on record and not just in a chat message. "
        "Never record anything about performance, attitude or a medical reason — "
        "dates and the founder's own words only."
    )
    args_schema: type[BaseModel] = WellbeingInput

    def _run(self, person: str, type: str, note: str = "",
             start_date: Optional[str] = None, end_date: Optional[str] = None) -> str:
        try:
            valid = ("leave", "sick", "overloaded", "flagged", "override_approved")
            if type not in valid:
                raise RosterError(f"'{type}' is not an event type. Use one of: {', '.join(valid)}.")
            who = get_person(person)
            if not who:
                names = ", ".join(p["name"] for p in get_team_roster())
                raise RosterError(f"No one named '{person}' is in the roster. The team is: {names}.")
            if type in ("leave", "sick") and not (start_date and end_date):
                raise RosterError("Leave and sick events need both start_date and end_date.")
            span = f" from {start_date} to {end_date}" if start_date else ""
            return f"Logged '{type}' for {who['name']}{span}."
        except Exception as exc:
            return f"ERROR: {exc}"


log_wellbeing_event = LogWellbeingEvent()
tool = log_wellbeing_event
