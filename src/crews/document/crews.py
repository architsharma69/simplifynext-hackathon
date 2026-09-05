"""
crews/crews.py
Thin Crew wrappers around each sub-agent. Each function builds a fresh Crew
per invocation (CrewAI Crews are cheap to construct) and returns the raw
kickoff output as a string for the Flow to parse. Kept as one-agent Crews
for now since there's no intra-domain delegation yet (e.g. Statutory doesn't
delegate to a sub-specialist) — but structuring them as Crews rather than
bare Agent.execute() calls means adding delegation later is a non-breaking
change from the Flow's point of view.
"""
from __future__ import annotations

import json

from crewai import Crew, Process

from crews.document.agents import (
    financial_synthesizer_agent,
    grant_strategist_agent,
    statutory_compliance_agent,
)
from crews.document.tasks import make_financial_task, make_grant_tasks, make_statutory_tasks


def run_statutory_crew(company_profile_json: str, document_types: list[str]) -> str:
    tasks = make_statutory_tasks(document_types)
    crew = Crew(
        agents=[statutory_compliance_agent],
        tasks=tasks,
        process=Process.sequential,
        verbose=True,
    )
    result = crew.kickoff(inputs={"company_profile_json": company_profile_json})
    return str(result)


def run_financial_crew(financial_assumptions: dict) -> str:
    task = make_financial_task()
    crew = Crew(
        agents=[financial_synthesizer_agent],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
    )
    result = crew.kickoff(
        inputs={"financial_assumptions_json": json.dumps(financial_assumptions)}
    )
    return str(result)


def run_grant_crew(
    scheme: str,
    company_profile_json: str,
    financial_forecast_json: str,
    headcount_plan_json: str,
    narrative_sections: dict,
    requested_amount_sgd: float,
) -> str:
    tasks = make_grant_tasks(scheme)
    crew = Crew(
        agents=[grant_strategist_agent],
        tasks=tasks,
        process=Process.sequential,
        verbose=True,
    )
    result = crew.kickoff(
        inputs={
            "company_profile_json": company_profile_json,
            "financial_forecast_json": financial_forecast_json,
            "headcount_plan_json": headcount_plan_json,
            "narrative_sections_json": json.dumps(narrative_sections),
            "requested_amount_sgd": requested_amount_sgd,
        }
    )
    return str(result)
