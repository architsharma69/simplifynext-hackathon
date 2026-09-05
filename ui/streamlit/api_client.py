import httpx

TIMEOUT_SECONDS = 60.0


class OrchestratorError(Exception):
    """Raised when the FastAPI backend can't be reached or returns an error."""


def send_message(base_url: str, user_id: str, message: str) -> dict:
    try:
        resp = httpx.post(
            f"{base_url}/chat",
            json={"platform": "streamlit", "user_id": user_id, "message": message},
            timeout=TIMEOUT_SECONDS,
        )
    except httpx.RequestError as exc:
        raise OrchestratorError(f"Could not reach the orchestrator API: {exc}") from exc

    if resp.status_code != 200:
        raise OrchestratorError(
            f"Orchestrator API returned {resp.status_code}: {resp.text}"
        )

    return resp.json()
