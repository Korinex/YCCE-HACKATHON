from __future__ import annotations

from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .schemas import AnalyzeResponse, RedactRequest, RedactResponse
from .session import SessionStore, create_session, delete_session, get_session

app = FastAPI(title="PS-06 Privacy Shield API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
def _shutdown() -> None:
    SessionStore().shutdown()


@app.get("/api/v1/health")
def health() -> dict[str, bool | str]:
    return {"status": "ok", "ocr_available": False}


@app.post("/api/v1/session")
async def create_session_route(request: Request) -> dict[str, Any]:
    payload = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    content_type = payload.get("content_type", "text")
    ttl_seconds = int(payload.get("ttl_seconds", 600))
    if content_type not in {"text", "image", "pdf"}:
        raise HTTPException(422, "content_type must be text, image, or pdf")
    session = create_session(content_type=content_type, content=payload.get("content"), ttl_seconds=ttl_seconds)
    return {"status": "ok", "request_id": session.request_id, "ttl_seconds": ttl_seconds}


@app.get("/api/v1/session/{request_id}")
def get_session_route(request_id: str) -> dict[str, Any]:
    session = get_session(request_id)
    if session is None:
        raise HTTPException(404, "Unknown request ID")
    ttl = max(int((session.expires_at - session.created_at).total_seconds()), 0)
    return {"status": "ok", "request_id": session.request_id, "content_type": session.content_type, "ttl_seconds": ttl}


@app.delete("/api/v1/session/{request_id}")
def delete_session_route(request_id: str) -> dict[str, str]:
    if get_session(request_id) is None:
        raise HTTPException(404, "Unknown request ID")
    delete_session(request_id)
    return {"status": "deleted", "request_id": request_id}


@app.post("/api/v1/analyze", response_model=AnalyzeResponse)
async def analyze(
    content_type: str = Form(...),
    text: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
) -> AnalyzeResponse:
    if content_type not in {"text", "image", "pdf"}:
        raise HTTPException(422, "content_type must be text, image, or pdf")
    if content_type == "text" and not (text and text.strip()):
        raise HTTPException(422, "Text content is required")
    if content_type == "image" and file is None:
        raise HTTPException(422, "An image file is required")
    raise HTTPException(501, "Analysis pipeline is not implemented in the skeleton")


@app.post("/api/v1/redact", response_model=RedactResponse)
def redact(payload: RedactRequest) -> RedactResponse:
    if get_session(payload.request_id) is None:
        raise HTTPException(404, "Unknown request ID")
    raise HTTPException(501, "Redaction engine is not implemented in the skeleton")


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "PS-06 Personal Data Privacy Shield", "status": "skeleton"}
