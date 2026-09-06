"""
crews/hr/tools/get_person_workload.py
CrewAI tool wrapper — read.

Referenced from crews/hr/agents.py as one of hr_manager_agent's tools.
Ported from plan/workload_manager/tools/get_person_workload.py — only the
import of the underlying ledger function changed.
"""

import json
from typing import Optional

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crews.hr.ledger import get_person_workload as _get_person_workload


class WorkloadInput(BaseModel):
    name: str = Field(
        ..., description="Full name of the person, exactly as it appears in the roster."
    )
    week: Optional[str] = Field(
        None,
        description="ISO week such as 2026-W36. Leave empty for the current week. "
                    "This is a week, not a date — convert a date to its week first.",
    )


class GetPersonWorkload(BaseTool):
    name: str = "get_person_workload"

    description: str = (
        "How loaded is one person in one week. Returns committed hours, effective "
        "capacity (already reduced for logged leave), load_pct as a decimal where "
        "1.18 means 118%, the number of consecutive overloaded weeks behind them, "
        "and the open tasks making up that load. "
        "Use this when the founder asks about a specific person, and to quote real "
        "numbers back to them. It reports the CURRENT state — it does not tell you "
        "whether adding work is safe, so it never replaces check_assignment_safety."
    )
    args_schema: type[BaseModel] = WorkloadInput

    def _run(self, name: str, week: Optional[str] = None) -> str:
        try:
            return json.dumps(_get_person_workload(name, week), indent=2, default=str)
        except Exception as exc:
            return f"ERROR: {exc}"


get_person_workload = GetPersonWorkload()
tool = get_person_workload
