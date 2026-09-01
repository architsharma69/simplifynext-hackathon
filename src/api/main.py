import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from api.entrypoint import run_orchestrator
from api.sessions import get_session, save_session

logger = logging.getLogger(__name__)

app = FastAPI(title="BRO Orchestrator API")


class ChatRequest(BaseModel):
    platform: str
    user_id: str
    message: str


class ChatResponse(BaseModel):
    response: str
    metadata: dict


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    session_state = get_session(req.platform, req.user_id)

    try:
        result = run_orchestrator(req.message, session_state)
    except Exception:
        logger.exception(
            "orchestrator failed for platform=%s user_id=%s", req.platform, req.user_id
        )
        return JSONResponse(
            status_code=500,
            content={
                "response": "Something went wrong processing your request.",
                "metadata": {},
            },
        )

    save_session(req.platform, req.user_id, result["session_state"])
    logger.info(
        "platform=%s user_id=%s invoked_specialists=%s",
        req.platform,
        req.user_id,
        result["invoked_specialists"],
    )

    return ChatResponse(
        response=result["response"],
        metadata={"invoked_specialists": result["invoked_specialists"]},
    )
