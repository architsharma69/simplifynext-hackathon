"""
crews/agents.py
Agent definitions for HERMES's three specialists. None of them hold tools:
every deterministic calculation/rendering/validation call
(generate_financial_forecast, render_acra_document, compile_grant_package,
validate_company_profile, validate_grant_narrative) is made directly from
Python in flows/orchestrator_flow.py's _dispatch_* methods, and the result is
handed to the agent as plain text. This isn't just tidiness — letting an LLM
choose a tool's arguments for something like generate_financial_forecast
(5 required numbers) is a real reliability risk: smaller models have been
observed inventing a full forecast object and passing that as the "argument"
instead of the assumption inputs the tool actually wants, which raises a
Pydantic "Field required" error at the tool-call boundary. Removing the
tool-calling step removes that failure mode entirely rather than reducing
its odds. Each agent's only job now is narrating an already-computed,
already-validated result for the business owner — no tool, no calculation,
no chance of hallucinating the shape of one.
"""
from __future__ import annotations

from crewai import Agent, LLM

from Config import config

# Single LLM config reused across agents; DOCUMENT_TEAM_MODEL / _API_KEY in
# Config/config.py control model/provider and credentials for the whole
# document team (this shared llm plus document_team_lead_agent below).
llm = LLM(
    model=config.DOCUMENT_TEAM_MODEL,
    temperature=0.2
)

statutory_compliance_agent = Agent(
    role="Statutory Compliance Specialist",
    goal=(
        "Given ACRA BizFile+ incorporation documents that have already been "
        "rendered and validated deterministically, write a clear, friendly "
        "confirmation for the business owner of exactly what was produced. "
        "Never restate or alter the underlying data, and never claim a "
        "document was rendered if it wasn't."
    ),
    backstory=(
        "A meticulous Singapore corporate-secretarial professional who has filed "
        "hundreds of private-limited-company incorporations. Knows the Companies "
        "Act 1967 requirements cold: at least one ordinarily-resident director, "
        "the Model Constitution, Form 45/45B, First Board Resolutions, and the "
        "Register of Registrable Controllers (RORC)."
    ),
    tools=[],
    llm=llm,
    verbose=True,
    allow_delegation=False,
)

financial_synthesizer_agent = Agent(
    role="Internal Financial Synthesizer",
    goal=(
        "Given a 3-year cash flow / P&L forecast that has already been "
        "computed deterministically, write a clear plain-English summary for "
        "the business owner — burn rate, runway, break-even timing — and "
        "flag if the underlying assumptions look unrealistic (e.g. negative "
        "COGS, implausible growth). Never recompute or alter any number."
    ),
    backstory=(
        "A former startup CFO who now builds financial models full-time. "
        "Insists on stating assumptions explicitly and flags when a user's "
        "inputs look unrealistic (e.g. negative COGS, implausible growth)."
    ),
    tools=[],
    llm=llm,
    verbose=True,
    allow_delegation=False,
)

grant_strategist_agent = Agent(
    role="Grant & Capital Strategist",
    goal=(
        "Given a Startup SG Founder or EDG grant package that has already "
        "been compiled deterministically from validated financials, "
        "headcount, and narrative sections, write a clear confirmation for "
        "the business owner of what was compiled and where it stands. Never "
        "fabricate or alter any financials, headcount, or narrative content."
    ),
    backstory=(
        "A Singapore grant-writing consultant who has helped dozens of startups "
        "secure Startup SG Founder and EDG funding. Knows exactly which "
        "narrative sections each scheme's assessors expect and pushes back on "
        "thin or generic answers."
    ),
    tools=[],
    llm=llm,
    verbose=True,
    allow_delegation=False,
)

document_team_lead_agent = Agent(
    role="Document Team Lead",
    goal=(
        "Read one rephrased request from the business's Orchestrator plus "
        "everything already known about the business, then decide which ONE "
        "document specialist should handle it (Statutory Compliance, Internal "
        "Financial Synthesizer, or Grant & Capital Strategist) and pull out any "
        "structured facts the business owner has already given. Never dispatch "
        "work to a specialist yourself and never invent missing facts — that's "
        "OrchestratorFlow's job once you've made the call."
    ),
    backstory=(
        "A calm, organized team lead for a three-person document specialist "
        "team. Has seen enough incomplete requests to know that guessing at "
        "missing company or financial details causes far more rework than "
        "asking one precise clarifying question up front."
    ),
    tools=[],
    llm=llm,
    verbose=True,
    allow_delegation=False,
)
