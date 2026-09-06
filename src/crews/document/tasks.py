"""
crews/document/tasks.py
Prompt-text builders for the Document Team Lead and each document specialist.
These return plain strings for Agent.kickoff(...) calls — no crewai.Task or
Crew objects — because dispatch and sequencing are handled directly by
OrchestratorFlow (flows/orchestrator_flow.py), and each specialist is a
standalone Agent (crews/document/agents.py) invoked on its own, not
coordinated through a Crew.
"""
from __future__ import annotations

import json


def build_document_routing_prompt(sub_query: str, business_context: dict) -> str:
    return (
        "A business owner's question, already rephrased for the document team, is:\n"
        f'"{sub_query}"\n\n'
        f"Anything already known from earlier in the conversation (JSON): {json.dumps(business_context)}\n\n"
        "Decide which ONE document specialist should handle this:\n"
        '- "statutory": Singapore ACRA BizFile+ incorporation paperwork (Model '
        "Constitution, Form 45, Form 45B, First Board Resolution, RORC register). "
        "If this is the one, list which document type(s) were asked for in "
        "document_types.\n"
        '- "financial": a 3-year cash flow / P&L forecast, burn rate, and '
        "break-even estimate.\n"
        '- "grant": a Startup SG Founder or EDG grant package. If this is the '
        "one, set grant_scheme "
        '("startup_sg_founder" or "enterprise_development_grant") and '
        "requested_amount_sgd from whatever the owner has said (leave either "
        "null if not yet known — that's fine, don't guess).\n\n"
        "The company profile, financial assumptions, grant narrative, and "
        "headcount plan themselves are NOT something you need to gather or "
        "extract — each specialist already has its own reference data for "
        "this business and loads it directly. Your job is only to pick the "
        "specialist and, for statutory/grant, the request-specific choices "
        "above.\n\n"
        'If you can tell which specialist applies, set route_type to "dispatch". '
        "If you genuinely cannot tell even from the rephrased question, set "
        'route_type to "clarify" and ask exactly one specific question in '
        "clarifying_question."
    )


def build_statutory_summary_prompt(
    document_types: list[str], rendered_documents_json: list[str]
) -> str:
    """rendered_documents_json: one RenderedDocument JSON string per document
    already rendered by render_acra_document (called directly in Python —
    see flows/orchestrator_flow.py._dispatch_statutory). The agent only
    narrates this; it has no render tool of its own.
    """
    return (
        f"The following ACRA documents have already been rendered and saved "
        f"(requested types: {', '.join(document_types)}):\n\n"
        + "\n".join(rendered_documents_json)
        + "\n\nWrite one short, friendly sentence per document confirming "
        "what was produced for the business owner. Do not restate the JSON "
        "verbatim, do not invent additional details, and do not claim "
        "anything was rendered beyond what's listed above."
    )


def build_financial_summary_prompt(financial_forecast_json: str, burn_summary: str) -> str:
    """financial_forecast_json / burn_summary: already computed by
    generate_financial_forecast / summarize_burn_and_breakeven, called
    directly in Python (see _dispatch_financial). The agent only narrates
    and sanity-checks the assumptions embedded in the forecast; it has no
    calculation tool of its own.
    """
    return (
        "The 3-year cash flow / P&L forecast below has already been "
        "generated deterministically — do not recompute or alter any "
        f"numbers in it:\n\n{financial_forecast_json}\n\n"
        f"Deterministic burn/runway/break-even summary: {burn_summary}\n\n"
        "Using only these numbers (the forecast's own `assumptions` field "
        "has the inputs it was built from), write a short plain-English "
        "paragraph for the business owner. If any of the underlying "
        "assumptions looks implausible (e.g. >50% monthly growth sustained "
        "for 36 months), say so explicitly."
    )


def build_grant_summary_prompt(grant_package_json: str) -> str:
    """grant_package_json: already compiled by compile_grant_package, called
    directly in Python (see _dispatch_grant). The agent only narrates; it
    has no compile tool of its own.
    """
    return (
        "The grant package below has already been compiled and saved "
        f"deterministically:\n\n{grant_package_json}\n\n"
        "Write a short, friendly confirmation for the business owner "
        "summarizing what was compiled and where it stands. Do not restate "
        "the JSON verbatim, and do not recompute or alter any of the "
        "figures, narrative content, or headcount."
    )
