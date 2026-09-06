"""
crews/hr/tools/get_capacity_forecast.py
CrewAI tool wrapper — read.

Referenced from crews/hr/agents.py as one of hr_manager_agent's tools.
Ported from plan/workload_manager/tools/get_capacity_forecast.py — only the
import of the underlying ledger function changed.
"""

import json

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crews.hr.ledger import get_capacity_forecast as _get_capacity_forecast


class ForecastInput(BaseModel):
    weeks: int = Field(
        4,
        ge=1,
        le=12,
        description="How many weeks ahead to look, starting with the current week.",
    )


class GetCapacityForecast(BaseTool):
    name: str = "get_capacity_forecast"

    description: str = (
        "Committed hours against capacity for every person, for the next N weeks. "
        "One row per person per week, with load_pct as a decimal. "
        "Use this to answer 'who has room', 'when does this get better', or to pick "
        "a later week for work that will not fit now. "
        "This is NOT a prediction: it counts only work already in the ledger, so a "
        "quiet week ahead means nothing has been booked yet, not that the week is "
        "genuinely free."
    )
    args_schema: type[BaseModel] = ForecastInput

    def _run(self, weeks: int = 4) -> str:
        try:
            return json.dumps(_get_capacity_forecast(weeks), indent=2, default=str)
        except Exception as exc:
            return f"ERROR: {exc}"


get_capacity_forecast = GetCapacityForecast()
tool = get_capacity_forecast
