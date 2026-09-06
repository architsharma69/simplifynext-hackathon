"""Stand-ins for the specialist crews that don't exist yet.

Every function here is a placeholder: canned strings, no CrewAI Agent/Task/Crew,
no prompts, no LLM calls. They exist so the Flow's control structure can be
built and tested before the real specialist crews exist.

Finance and Consultant are still placeholders. The Orchestrator (see
crews/orchestrator/agent.py), the document team (crews/document/) and the HR
workload manager (crews/hr/) are real -- OrchestratorFlow calls those directly
and no longer imports a placeholder for them.
"""


def run_finance(sub_query: str) -> str:
    return f"[Finance placeholder] would respond to: {sub_query}"


def run_consultant() -> str:
    return "[Consultant placeholder] no improvements proposed yet."
