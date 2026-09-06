from api import documents
from flows.orchestrator_flow import OrchestratorFlow

CROSS_TURN_FIELDS = ("conversation_history", "business_context", "pending_actions")


def run_orchestrator(user_input: str, session_state: dict | None = None) -> dict:
    carried_over = {
        field: value
        for field, value in (session_state or {}).items()
        if field in CROSS_TURN_FIELDS
    }

    flow = OrchestratorFlow()
    flow.kickoff(inputs={"user_input": user_input, **carried_over})

    flow.state.conversation_history.append(
        {"user": user_input, "response": flow.state.final_response}
    )

    generated_documents = [
        {
            "document_type": doc["document_type"],
            "filename": doc["filename"],
            "document_id": documents.register_document(doc["file_path"]),
        }
        for doc in flow.state.generated_documents
    ]

    return {
        "response": flow.state.final_response,
        "invoked_specialists": flow.state.invoked_specialists,
        "generated_documents": generated_documents,
        "session_state": {
            field: getattr(flow.state, field) for field in CROSS_TURN_FIELDS
        },
    }
