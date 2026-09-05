"""Stand-ins for the specialist crews (README Section 3+).

Every function here is a placeholder: canned strings, no CrewAI Agent/Task/Crew,
no prompts, no LLM calls. They exist so the Flow's control structure can be
built and tested before the real specialist crews exist. The Orchestrator
itself is real — see src/crews/orchestrator/agent.py.
"""


def run_hr(sub_query: str) -> str:
    return f"[HR placeholder] would respond to: {sub_query}"


def run_finance(sub_query: str) -> str:
    return f"[Finance placeholder] would respond to: {sub_query}"


def run_document(sub_query: str) -> str:
    return f"[Document placeholder] would respond to: {sub_query}"


def run_consultant() -> str:
    return "[Consultant placeholder] no improvements proposed yet."
