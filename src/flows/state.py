from pydantic import BaseModel


class OrchestratorState(BaseModel):
    conversation_history: list[dict] = []
    active_agent_outputs: dict[str, str] = {}
    pending_actions: list[str] = []
    business_context: dict = {}

    user_input: str = ""
    routing_decision: dict = {}
    invoked_specialists: list[str] = []
    final_response: str = ""
    # Files rendered by the document specialists this turn, e.g.
    # {"document_type": ..., "filename": ..., "file_path": ...}. Per-turn
    # like active_agent_outputs/invoked_specialists — not carried cross-turn.
    generated_documents: list[dict] = []
