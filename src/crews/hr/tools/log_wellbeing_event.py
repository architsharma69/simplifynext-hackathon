"""
crews/hr/tools/log_wellbeing_event.py
CrewAI tool wrapper — write.

Leave logged here immediately reduces that person's effective capacity, which
means the next safety check refuses work the previous one would have allowed.
That is the point: this is how the guardrail learns about the world.

Referenced from crews/hr/agents.py as one of hr_manager_agent's tools.
Ported from plan/workload_manager/tools/log_wellbeing_event.py — only the
import of the underlying ledger function changed.
"""

import json
from typing import Optional

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crews.hr.ledger import log_wellbeing_event as _log_wellbeing_event


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
        "Record leave, sickness, an overload concern, or an approved override "
        "against a person. "
        "Logging leave or sickness cuts that person's capacity for those days "
        "straight away, so do it BEFORE placing any work in that window. "
        "Log 'flagged' when you tell the founder somebody is carrying too much, so "
        "the pattern is on record and not just in a chat message. "
        "Never record anything about performance, attitude or a medical reason — "
        "dates and the founder's own words only."
    )
    args_schema: type[BaseModel] = WellbeingInput

    def _run(self, person: str, type: str, note: str = "",
             start_date: Optional[str] = None, end_date: Optional[str] = None) -> str:
        try:
            result = _log_wellbeing_event(person, type, note, start_date, end_date)
            return json.dumps(result, indent=2, default=str)
        except Exception as exc:
            return f"ERROR: {exc}"


log_wellbeing_event = LogWellbeingEvent()
tool = log_wellbeing_event
