"""
crews/agents.py
Agent definitions for HERMES's three specialists. Each agent is scoped to a
narrow toolset on purpose — the Statutory agent cannot touch grant tools,
the Grant agent cannot render ACRA forms directly, etc. This keeps the
delegation graph inside each Crew shallow and makes prompt-injection /
scope-creep failures easier to reason about.
"""
from __future__ import annotations

from crewai import Agent, LLM

from crews.document.tools.statutory_tools import render_acra_document, validate_company_profile
from crews.document.tools.financial_tools import (
    generate_financial_forecast,
    summarize_burn_and_breakeven,
)
from crews.document.tools.grant_tools import validate_grant_narrative, compile_grant_package

# Single LLM config reused across agents; swap model/provider here.
llm = LLM(model="claude-sonnet-4-6", temperature=0.2)

statutory_compliance_agent = Agent(
    role="Statutory Compliance Specialist",
    goal=(
        "Collect and validate everything needed to file Singapore ACRA BizFile+ "
        "incorporation paperwork, then render the required documents exactly. "
        "Never invent director/shareholder details the user has not provided; "
        "ask instead of guessing."
    ),
    backstory=(
        "A meticulous Singapore corporate-secretarial professional who has filed "
        "hundreds of private-limited-company incorporations. Knows the Companies "
        "Act 1967 requirements cold: at least one ordinarily-resident director, "
        "the Model Constitution, Form 45/45B, First Board Resolutions, and the "
        "Register of Registrable Controllers (RORC)."
    ),
    tools=[validate_company_profile, render_acra_document],
    llm=llm,
    verbose=True,
    allow_delegation=False,
)

financial_synthesizer_agent = Agent(
    role="Internal Financial Synthesizer",
    goal=(
        "Turn a small set of business assumptions into a rigorous 3-year cash "
        "flow / P&L forecast, burn rate, and break-even estimate — using the "
        "calculation tool, never mental arithmetic — so downstream agents can "
        "rely on the numbers."
    ),
    backstory=(
        "A former startup CFO who now builds financial models full-time. "
        "Insists on stating assumptions explicitly and flags when a user's "
        "inputs look unrealistic (e.g. negative COGS, implausible growth)."
    ),
    tools=[generate_financial_forecast, summarize_burn_and_breakeven],
    llm=llm,
    verbose=True,
    allow_delegation=False,
)

grant_strategist_agent = Agent(
    role="Grant & Capital Strategist",
    goal=(
        "Compile a complete, compelling Startup SG Founder or EDG grant package "
        "using the financial forecast and headcount plan already produced by "
        "other specialists — never fabricate financials or headcount, only "
        "reference what has already been generated."
    ),
    backstory=(
        "A Singapore grant-writing consultant who has helped dozens of startups "
        "secure Startup SG Founder and EDG funding. Knows exactly which "
        "narrative sections each scheme's assessors expect and pushes back on "
        "thin or generic answers."
    ),
    tools=[validate_grant_narrative, compile_grant_package],
    llm=llm,
    verbose=True,
    allow_delegation=False,
)
