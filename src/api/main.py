import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from api import documents
from api.entrypoint import run_orchestrator
from api.sessions import get_session, save_session
from Config.config import DOCUMENT_OUTPUT_DIR

logger = logging.getLogger(__name__)

app = FastAPI(title="BRO Orchestrator API")

_DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


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
        metadata={
            "invoked_specialists": result["invoked_specialists"],
            "documents": result["generated_documents"],
        },
    )


@app.get("/documents/{document_id}")
def download_document(document_id: str):
    file_path = documents.get_document_path(document_id)
    if file_path is None:
        return JSONResponse(status_code=404, content={"detail": "Unknown document_id"})

    resolved = Path(file_path).resolve()
    output_dir = Path(DOCUMENT_OUTPUT_DIR).resolve()
    if output_dir not in resolved.parents or not resolved.is_file():
        return JSONResponse(status_code=404, content={"detail": "Document not found"})

    return FileResponse(
        resolved, filename=os.path.basename(resolved), media_type=_DOCX_MEDIA_TYPE
    )
