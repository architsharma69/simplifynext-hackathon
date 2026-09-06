import httpx

# Orchestrator turns can involve multiple LLM/agent calls and occasionally
# take several minutes, so this needs to be generous rather than a typical
# HTTP request timeout. Mirrors ui/streamlit/api_client.py.
TIMEOUT_SECONDS = 300.0


class OrchestratorError(Exception):
    """Raised when the FastAPI backend can't be reached or returns an error."""


async def send_message(base_url: str, user_id: str, message: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            resp = await client.post(
                f"{base_url}/chat",
                json={"platform": "telegram", "user_id": user_id, "message": message},
            )
    except httpx.RequestError as exc:
        raise OrchestratorError(f"Could not reach the orchestrator API: {exc}") from exc

    if resp.status_code != 200:
        raise OrchestratorError(
            f"Orchestrator API returned {resp.status_code}: {resp.text}"
        )

    return resp.json()
