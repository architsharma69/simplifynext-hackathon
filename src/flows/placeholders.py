"""Stand-ins for the real Orchestrator agent and specialist crews (README Section 2/3+).

Every function here is a placeholder: keyword matching and canned strings, no
CrewAI Agent/Task/Crew, no prompts, no LLM calls. They exist so the Flow's
control structure can be built and tested before the real agents exist.
"""

HR_KEYWORDS = ("hr", "employee", "roster", "staff")
FINANCE_KEYWORDS = ("finance", "budget", "expense", "invoice")
DOCUMENT_KEYWORDS = ("document", "form", "report", "grant", "loan")


def classify_intent(user_input: str) -> dict:
    text = user_input.lower()

    specialists = []
    if any(kw in text for kw in HR_KEYWORDS):
        specialists.append("hr")
    if any(kw in text for kw in FINANCE_KEYWORDS):
        specialists.append("finance")
    if any(kw in text for kw in DOCUMENT_KEYWORDS):
        specialists.append("document")

    needs_clarification = not specialists
    return {
        "specialists": specialists,
        "needs_clarification": needs_clarification,
        "clarifying_question": (
            "Could you clarify whether this is an HR, Finance, or Document request?"
            if needs_clarification
            else None
        ),
    }


def run_hr(sub_query: str) -> str:
    return f"[HR placeholder] would respond to: {sub_query}"


def run_finance(sub_query: str) -> str:
    return f"[Finance placeholder] would respond to: {sub_query}"


def run_document(sub_query: str) -> str:
    return f"[Document placeholder] would respond to: {sub_query}"


def run_consultant() -> str:
    return "[Consultant placeholder] no improvements proposed yet."


def synthesize(outputs: dict[str, str]) -> str:
    if not outputs:
        return "No specialist responses to synthesize."
    return "\n".join(f"[{name}] {text}" for name, text in outputs.items())
