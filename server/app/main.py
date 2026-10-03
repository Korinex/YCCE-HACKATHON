from __future__ import annotations

import base64
import binascii
import io
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Any, Protocol

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image

from .pdf_engine import inspect_pdf, safe_pdf_filename, sanitize_pdf_bytes
from .redact_engine import (
    render_image_redaction,
    render_text_redaction,
    safe_output_filename,
)
from .schemas import (
    AnalyzeResponse,
    AnalyzeSummary,
    AuditResult,
    InternalFinding,
    PublicFinding,
    ProtectionSummary,
    RedactRequest,
    RedactResponse,
    VerifyRequest,
    VerifyResponse,
)
from .session import SessionStore, create_session, delete_session, get_session

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class Backend2Analyzer(Protocol):
    def analyze_content(
        self,
        *,
        content: bytes | str,
        content_type: str,
        document_metadata: dict[str, Any],
        pdf_password: str | None = None,
    ) -> list[InternalFinding]:
        ...


class Backend3Verifier(Protocol):
    def verify_cleaned_output(
        self,
        *,
        original_session: Any,
        cleaned_bytes: bytes,
        cleaned_content_type: str,
        findings: list[InternalFinding],
    ) -> AuditResult:
        ...


class PipelineAdapter:
    """Typed adapter around Backend 2's stable ``analyze_content`` handoff."""

    def analyze_content(
        self,
        *,
        content: bytes | str,
        content_type: str,
        document_metadata: dict[str, Any],
        pdf_password: str | None = None,
    ) -> list[InternalFinding]:
        from .pipeline import analyze_content

        try:
            result = analyze_content(content_type, content)
        except NotImplementedError as exc:
            raise RuntimeError("Backend-2 detector is not available") from exc
        except ValueError:
            raise

        width = float(document_metadata.get("width", 0) or 0)
        height = float(document_metadata.get("height", 0) or 0)
        findings: list[InternalFinding] = []
        for candidate in result.get("detected_items", []):
            bbox = candidate.get("bounding_box")
            normalized_bbox = None
            if bbox is not None and width > 0 and height > 0:
                normalized_bbox = {
                    "x": float(bbox["x"]) / width,
                    "y": float(bbox["y"]) / height,
                    "w": float(bbox["w"]) / width,
                    "h": float(bbox["h"]) / height,
                }
            finding_type = candidate.get("type", "MEDICAL")
            if finding_type == "HEALTH_TERM":
                finding_type = "MEDICAL"
            elif finding_type not in {
                "AADHAAR", "PAN", "PHONE", "BANK_ACCOUNT", "IFSC", "UPI",
                "CREDIT_CARD", "EMAIL", "ADDRESS", "MEDICAL", "NAME",
            }:
                finding_type = "MEDICAL"
            findings.append(
                InternalFinding.model_validate(
                    {
                        "id": candidate["id"],
                        "type": finding_type,
                        "raw_value": candidate["raw_value"],
                        "value_masked": candidate.get("value_masked", "[REDACTED]"),
                        "masked_display": candidate.get("value_masked", "[REDACTED]"),
                        "raw_span": (
                            (candidate.get("start"), candidate.get("end"))
                            if candidate.get("start") is not None and candidate.get("end") is not None
                            else None
                        ),
                        "char_span": (
                            (candidate.get("start"), candidate.get("end"))
                            if candidate.get("start") is not None and candidate.get("end") is not None
                            else None
                        ),
                        "validity_class": candidate.get("validation_tier", "REVIEW"),
                        "is_valid": candidate.get("is_valid", False),
                        "validation_method": candidate.get("validation_method", "SCOUT"),
                        "validation_reason": candidate.get("validation_reason", ""),
                        "confidence": candidate.get("confidence", 0.0),
                        "confidence_band": candidate.get("confidence_band", "LOW"),
                        "bbox": normalized_bbox,
                        "action": candidate.get("action", "MASK"),
                        "context_hit": candidate.get("context_hit", []),
                        "sensitivity": candidate.get("sensitivity"),
                        "source": candidate.get("source", "text"),
                        "ocr_confidence": candidate.get("ocr_confidence"),
                        "page": candidate.get("page"),
                        "decided": False,
                    }
                )
            )
        return findings


class Backend3Adapter:
    """Translate Backend 3's dataclass result into the safe API contract."""

    def verify_cleaned_output(
        self,
        *,
        original_session: Any,
        cleaned_bytes: bytes,
        cleaned_content_type: str,
        findings: list[InternalFinding],
    ) -> AuditResult:
        from .verify_service import verify_cleaned_output

        result = verify_cleaned_output(
            original_session=original_session.model_dump(),
            cleaned_bytes=cleaned_bytes,
            cleaned_content_type=cleaned_content_type,
            findings=[finding.model_dump() for finding in findings],
        )
        checks = [
            {
                "id": check.name,
                "pass": check.status == "PASSED",
                "scope": check.method_note or None,
                "status": (
                    "unsupported" if check.status == "UNSUPPORTED" else "ran"
                ),
            }
            for check in result.checks
        ]
        residuals = [
            {
                "category": residual.category,
                "page": residual.page,
                "region": residual.region,
            }
            for residual in result.residuals
        ]
        rectangles_status = {
            "CLEAN": "PASS",
            "FAIL": "FAIL",
            "PARTIAL": "PARTIAL",
        }[result.verdict]
        note_parts = [*result.notes, *result.missing_interfaces]
        return AuditResult(
            checks=checks,
            rectangles_vs_findings=rectangles_status,
            residuals=residuals,
            verdict=result.verdict,
            ran=result.ran,
            method_note="; ".join(note_parts) or "Backend-3 verification checks completed",
            timestamp=result.timestamp,
        )


backend2_analyzer: Backend2Analyzer = PipelineAdapter()
backend3_verifier: Backend3Verifier = Backend3Adapter()


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    SessionStore().shutdown()


app = FastAPI(title="PS-06 Privacy Shield API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _read_limited(data: bytes | str | None) -> bytes:
    if data is None:
        return b""
    raw = data.encode("utf-8") if isinstance(data, str) else data
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Input exceeds the maximum upload size")
    return raw


def _confidence_band(confidence: float) -> str:
    if confidence >= 0.85:
        return "HIGH"
    if confidence >= 0.6:
        return "MEDIUM"
    return "LOW"


def _public_finding(finding: InternalFinding) -> PublicFinding:
    data = {
        key: value
        for key, value in finding.model_dump(exclude={"raw_value"}).items()
        if key in PublicFinding.model_fields
    }
    data["value_masked"] = finding.value_masked
    data["confidence_band"] = _confidence_band(finding.confidence)
    data["rule"] = finding.action
    data["reason"] = finding.validation_reason
    if finding.bbox is not None:
        data["bbox"] = finding.bbox.model_dump()
    return PublicFinding.model_validate(data)


def _pipeline_findings(
    *,
    content: bytes | str,
    content_type: str,
    document_metadata: dict[str, Any],
    pdf_password: str | None = None,
) -> list[InternalFinding]:
    try:
        return backend2_analyzer.analyze_content(
            content=content,
            content_type=content_type,
            document_metadata=document_metadata,
            pdf_password=pdf_password,
        )
    except RuntimeError as exc:
        raise HTTPException(503, "Backend-2 detection is not available") from exc
    except Exception as exc:
        raise HTTPException(503, "Analysis pipeline unavailable") from exc


def _validate_image(content: bytes) -> tuple[int, int]:
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
        with Image.open(io.BytesIO(content)) as image:
            return image.width, image.height
    except Exception as exc:
        raise HTTPException(422, "Invalid image data") from exc


@app.get("/api/v1/health")
def health() -> dict[str, bool | str]:
    try:
        import PIL  # noqa: F401

        pdf_available = True
    except ImportError:
        pdf_available = False
    return {
        "status": "ok",
        "ocr_available": False,
        "pdf_available": pdf_available,
        "qr_available": False,
        "mode": "LOCAL",
    }


@app.post("/api/v1/session")
async def create_session_route(request: Request) -> dict[str, Any]:
    payload = await request.json()
    content_type = payload.get("content_type", "text")
    ttl_seconds = int(payload.get("ttl_seconds", 600))
    if content_type not in {"text", "image", "pdf"}:
        raise HTTPException(422, "Unsupported content type")
    try:
        session = create_session(content_type=content_type, ttl_seconds=ttl_seconds)
    except (ValueError, OverflowError) as exc:
        raise HTTPException(429 if isinstance(exc, OverflowError) else 422, str(exc)) from exc
    return {"status": "ok", "request_id": session.request_id, "ttl_seconds": ttl_seconds}


@app.get("/api/v1/session/{request_id}")
def get_session_route(request_id: str) -> dict[str, Any]:
    session = get_session(request_id)
    if session is None:
        raise HTTPException(404, "Unknown or expired request ID")
    remaining = max(int((session.expires_at - datetime.now(timezone.utc)).total_seconds()), 0)
    return {"status": "ok", "request_id": request_id, "content_type": session.content_type, "ttl_seconds": remaining}


@app.delete("/api/v1/session/{request_id}")
def delete_session_route(request_id: str) -> dict[str, str]:
    if get_session(request_id) is None:
        raise HTTPException(404, "Unknown or expired request ID")
    delete_session(request_id)
    return {"status": "deleted", "request_id": request_id}


@app.post("/api/v1/analyze", response_model=AnalyzeResponse)
async def analyze(
    content_type: str = Form(...),
    text: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    password: str | None = Form(default=None),
) -> AnalyzeResponse:
    if content_type not in {"text", "image", "pdf"}:
        raise HTTPException(422, "Unsupported content type")
    if content_type == "text":
        raw = _read_limited(text)
        if not raw.strip():
            raise HTTPException(422, "Text content is required")
        content: str | bytes = text or ""
        metadata = {"kind": "text", "bytes": len(raw)}
        pipeline_content: bytes | str = text or ""
    else:
        if file is None:
            raise HTTPException(422, "A file is required")
        raw = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(raw) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Input exceeds the maximum upload size")
        if not raw:
            raise HTTPException(422, "Input file is empty")
        if content_type == "image":
            width, height = _validate_image(raw)
            content = raw
            metadata = {"kind": "image", "width": width, "height": height}
            pipeline_content = raw
        else:
            try:
                page_count = inspect_pdf(raw, password=password)
            except ValueError as exc:
                raise HTTPException(422, "Invalid or locked PDF") from exc
            content = raw
            metadata = {"kind": "pdf", "page_count": page_count}
            pipeline_content = raw
    findings = _pipeline_findings(
        content=pipeline_content,
        content_type=content_type,
        document_metadata=metadata,
        pdf_password=password,
    )
    try:
        session = create_session(content_type=content_type, content=content, metadata=metadata)
    except (ValueError, OverflowError) as exc:
        raise HTTPException(429, "Session capacity reached") from exc
    SessionStore().register_findings(session.request_id, findings)
    public = [_public_finding(item) for item in findings]
    breakdown: dict[str, int] = {}
    for item in findings:
        breakdown[item.type] = breakdown.get(item.type, 0) + 1
    return AnalyzeResponse(
        request_id=session.request_id,
        content_type=content_type,
        extracted_text=None,
        detected_items=public,
        summary=AnalyzeSummary(
            total_pii_found=len(findings),
            validated_pii_count=sum(item.is_valid for item in findings),
            risk_score="LOW",
            breakdown=breakdown,
        ),
        document_metadata=metadata,
    )


@app.post("/api/v1/redact", response_model=RedactResponse)
def redact(payload: RedactRequest) -> RedactResponse:
    session = get_session(payload.request_id)
    if session is None:
        raise HTTPException(404, "Unknown or expired request ID")
    seen: set[str] = set()
    decisions: dict[str, str] = {}
    allowed = {"MASK", "REMOVE", "KEEP", "UIDAI_FIRST8", "REPLACE_TOKEN"}
    finding_ids = {finding.id for finding in session.findings}
    for decision in payload.decisions:
        if set(decision) != {"id", "action", "decided_by_user"} or decision.get("decided_by_user") is not True:
            raise HTTPException(422, "Malformed decision")
        finding_id = decision["id"]
        action = decision["action"]
        if finding_id in seen or finding_id not in finding_ids or action not in allowed:
            raise HTTPException(422, "Invalid or duplicate decision")
        if payload.strict_mode and action == "KEEP":
            finding = next(item for item in session.findings if item.id == finding_id)
            if finding.sensitivity in {"HIGH", "CRITICAL"} or finding.type in {"AADHAAR", "PAN", "BANK_ACCOUNT", "CREDIT_CARD"}:
                raise HTTPException(422, "High-risk KEEP is blocked in strict mode")
        seen.add(finding_id)
        decisions[finding_id] = action
    if finding_ids and seen != finding_ids:
        raise HTTPException(422, "A decision is required for every finding")
    items = [finding.model_dump(exclude={"raw_value"}) | {"action": decisions.get(finding.id, finding.action)} for finding in session.findings]
    rules = [{"id": key, "action": value} for key, value in decisions.items()]
    if session.content_type == "text":
        output = render_text_redaction(str(session.content), items, rules).encode("utf-8")
        filename = safe_output_filename("txt")
        return_value = {"sanitized_text": output.decode("utf-8"), "sanitized_file_b64": None}
    elif session.content_type == "image":
        output = render_image_redaction(bytes(session.content), items, rules)
        filename = safe_output_filename("png")
        return_value = {"sanitized_text": None, "sanitized_file_b64": base64.b64encode(output).decode("ascii")}
    else:
        output = sanitize_pdf_bytes(
            bytes(session.content),
            findings=items,
            mode="page_images",
        )
        filename = safe_pdf_filename()
        return_value = {"sanitized_text": None, "sanitized_file_b64": base64.b64encode(output).decode("ascii")}
    delete_session(payload.request_id)
    return RedactResponse(
        **return_value,
        download_filename=filename,
        protection_summary=ProtectionSummary(
            protected_records_count=len(decisions),
            breakdown={item.type: sum(1 for finding in session.findings if finding.type == item.type) for item in session.findings},
        ),
    )


@app.post("/api/v1/verify", response_model=VerifyResponse)
def verify(payload: VerifyRequest) -> VerifyResponse:
    session = get_session(payload.request_id)
    if session is None:
        raise HTTPException(404, "Unknown or expired request ID")
    if not payload.cleaned_bytes_b64:
        delete_session(payload.request_id)
        return VerifyResponse(
            status="blocked",
            request_id=payload.request_id,
            verdict="PARTIAL",
            block_reason="missing_cleaned_output",
            sanitized_file_b64=None,
        )
    try:
        cleaned = base64.b64decode(payload.cleaned_bytes_b64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(422, "Invalid cleaned output") from exc
    audit = backend3_verifier.verify_cleaned_output(
        original_session=session,
        cleaned_bytes=cleaned,
        cleaned_content_type=payload.cleaned_content_type,
        findings=session.findings,
    )
    residuals = [
        PublicFinding(
            id=f"residual-{index}",
            type=item.category if item.category in {
                "AADHAAR", "PAN", "PHONE", "BANK_ACCOUNT", "IFSC", "UPI",
                "CREDIT_CARD", "EMAIL", "ADDRESS", "MEDICAL", "NAME",
            } else "MEDICAL",
            value_masked="[REVIEW]",
            page=item.page,
            reason=item.region,
            validity_class="REVIEW",
        )
        for index, item in enumerate(audit.residuals)
    ]
    verdict = audit.verdict
    blocked = verdict == "FAIL" or (verdict == "PARTIAL" and payload.strict_mode)
    delete_session(payload.request_id)
    if blocked:
        return VerifyResponse(
            status="blocked",
            request_id=payload.request_id,
            verdict=verdict,
            block_reason="backend3_verification_failed" if verdict == "FAIL" else "backend3_verification_unavailable",
            sanitized_file_b64=None,
            residuals=residuals,
        )
    return VerifyResponse(
        request_id=payload.request_id,
        verdict=verdict,
        sanitized_file_b64=base64.b64encode(cleaned).decode("ascii"),
        residuals=residuals,
    )


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "PS-06 Personal Data Privacy Shield", "status": "ready"}
