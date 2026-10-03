from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .schemas import AnalyzeResponse, RedactRequest, RedactResponse

app = FastAPI(title="PS-06 Privacy Shield API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
def health() -> dict[str, bool | str]:
    return {"status": "ok", "ocr_available": False}


@app.post("/api/v1/analyze", response_model=AnalyzeResponse)
async def analyze(
    content_type: str = Form(...),
    text: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
) -> AnalyzeResponse:
    if content_type not in {"text", "image"}:
        raise HTTPException(422, "content_type must be text or image")
    if content_type == "text" and not (text and text.strip()):
        raise HTTPException(422, "Text content is required")
    if content_type == "image" and file is None:
        raise HTTPException(422, "An image file is required")
    raise HTTPException(501, "Analysis pipeline is not implemented in the skeleton")


@app.post("/api/v1/redact", response_model=RedactResponse)
def redact(_: RedactRequest) -> RedactResponse:
    raise HTTPException(501, "Redaction engine is not implemented in the skeleton")


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "PS-06 Personal Data Privacy Shield", "status": "skeleton"}
