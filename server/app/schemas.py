from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PIIType = Literal[
    "AADHAAR",
    "PAN",
    "PHONE",
    "BANK_ACCOUNT",
    "IFSC",
    "UPI",
    "CREDIT_CARD",
    "EMAIL",
    "ADDRESS",
    "MEDICAL",
    "NAME",
]
Action = Literal["MASK", "REMOVE", "KEEP", "UIDAI_FIRST8", "REPLACE_TOKEN"]
RiskScore = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
ContentType = Literal["text", "image", "pdf"]
ContextHit = Literal[
    "aadhaar",
    "pan",
    "phone",
    "bank_account",
    "ifsc",
    "upi",
    "credit_card",
    "name",
    "email",
    "address",
    "medical",
]
ValidityClass = Literal["VALIDATED", "FORMAT_ONLY", "REVIEW"]
ConfidenceBand = Literal["HIGH", "MEDIUM", "LOW"]
FindingSource = Literal["text", "ocr", "qr"]
QRStatus = Literal["UNVERIFIED", "UNSUPPORTED_AT_CARD"]

SESSION_TTL_SECONDS = 600
SESSION_TTL_SECONDS_DEMO = 1800
ALLOWED_CONTEXT_HITS = set(ContextHit.__args__)
FORBIDDEN_PUBLIC_FIELDS = {
    "raw_value",
    "original_filename",
    "raw_context",
    "deterministic_hash",
    "ocr_text",
    "password",
}


class BoundingBox(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    w: float = Field(ge=0.0, le=1.0)
    h: float = Field(ge=0.0, le=1.0)


class InternalFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: PIIType
    raw_value: str
    value_masked: str
    masked_display: str | None = None
    raw_span: tuple[int, int] | None = None
    validity_class: ValidityClass = "REVIEW"
    is_valid: bool = False
    validation_method: str = "manual"
    validation_reason: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_band: ConfidenceBand = "LOW"
    char_span: tuple[int, int] | None = None
    bbox: BoundingBox | None = None
    action: Action = "MASK"
    context_hit: ContextHit | list[ContextHit] | None = None
    sensitivity: str | None = None
    source: FindingSource | None = None
    page: int | None = None
    ocr_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    default_action: Literal["MASK"] = "MASK"
    decided: bool = False
    qr_status: QRStatus | None = None

    @model_validator(mode="after")
    def normalize_internal_finding(self) -> "InternalFinding":
        if self.masked_display is None:
            self.masked_display = self.value_masked
        if self.raw_span is None:
            self.raw_span = self.char_span
        return self


class PublicFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: PIIType
    value_masked: str
    masked_display: str | None = None
    is_valid: bool = False
    validation_method: str = "manual"
    validation_reason: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_band: ConfidenceBand = "LOW"
    char_span: tuple[int, int] | None = None
    bbox: dict[str, float] | None = None
    context_hit: ContextHit | list[ContextHit] | None = None
    sensitivity: str | None = None
    source: str | None = None
    page: int | None = None
    rule: str | None = None
    reason: str | None = None
    validity_class: ValidityClass = "REVIEW"
    ocr_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    qr_status: QRStatus | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_forbidden_public_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            forbidden = set(data) & FORBIDDEN_PUBLIC_FIELDS
            if forbidden:
                raise ValueError(f"Forbidden public fields: {sorted(forbidden)}")
            if data.get("masked_display") is None and data.get("value_masked") is not None:
                data = {**data, "masked_display": data["value_masked"]}
        return data


class SessionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    content_type: ContentType
    created_at: datetime
    expires_at: datetime
    original_content: bytes | str
    findings: list[InternalFinding] = Field(default_factory=list)
    document_metadata: dict[str, Any] = Field(default_factory=dict)
    ocr_metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def content(self) -> bytes | str:
        return self.original_content

    @property
    def metadata(self) -> dict[str, Any]:
        return self.document_metadata

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at


class AnalyzeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_pii_found: int = Field(ge=0)
    validated_pii_count: int = Field(ge=0)
    risk_score: RiskScore = "LOW"
    breakdown: dict[str, int] = Field(default_factory=dict)


class AnalyzeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["success"] = "success"
    request_id: str
    content_type: ContentType
    extracted_text: str | None = None
    detected_items: list[PublicFinding] = Field(default_factory=list)
    summary: AnalyzeSummary
    warnings: list[str] = Field(default_factory=list)
    document_metadata: dict[str, Any] = Field(default_factory=dict)


DetectedItem = PublicFinding


class RedactionRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    action: Action


class RedactRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    decisions: list[dict[str, Any]]
    strict_mode: bool = False


class ProtectionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protected_records_count: int = Field(ge=0)
    breakdown: dict[str, int] = Field(default_factory=dict)
    status: Literal["SECURED"] = "SECURED"


class RedactResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["success"] = "success"
    sanitized_text: str | None = None
    sanitized_file_b64: str | None = None
    download_filename: str | None = None
    protection_summary: ProtectionSummary
    block_reason: str | None = None


class ErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["error"] = "error"
    error: dict[str, Any]


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str | None = None
    content_type: ContentType = "text"
    text: str | None = None
    file_b64: str | None = None
    strict_mode: bool = False


class VerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    cleaned_content_type: ContentType = "text"
    cleaned_bytes_b64: str | None = None
    residual_findings: list[PublicFinding] = Field(default_factory=list)
    strict_mode: bool = False


class VerifyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["success", "blocked"] = "success"
    request_id: str
    verdict: Literal["CLEAN", "FAIL", "PARTIAL"] = "CLEAN"
    block_reason: str | None = None
    sanitized_file_b64: str | None = None
    residuals: list[PublicFinding] = Field(default_factory=list)


class AuditCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    passed: bool = Field(alias="pass")
    scope: str | None = None
    status: Literal["ran", "unsupported"] | None = None

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class AuditResidual(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    page: int | None = None
    region: str | None = None


class AuditResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checks: list[AuditCheck] = Field(default_factory=list)
    rectangles_vs_findings: Literal["PASS", "FAIL", "PARTIAL"]
    residuals: list[AuditResidual] = Field(default_factory=list)
    verdict: Literal["CLEAN", "FAIL", "PARTIAL"]
    ran: int = Field(ge=0)
    method_note: str
    timestamp: str


class SafeReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    app_version: str
    timestamp: datetime
    input_kind: str
    page_count: int = Field(ge=0)
    category_counts: dict[str, int] = Field(default_factory=dict)
    confidence_band_counts: dict[str, int] = Field(default_factory=dict)
    actions_by_category: dict[str, int] = Field(default_factory=dict)
    review_pages: list[int] = Field(default_factory=list)
    review_regions: list[str] = Field(default_factory=list)
    ocr_warnings: list[str] = Field(default_factory=list)
    residual_verdict: dict[str, Any] = Field(default_factory=dict)
    local_processing_only: bool = True
    session_ttl_seconds: int = SESSION_TTL_SECONDS
    kyc_advisory: str = "Local-only processing; do not treat as a legal certification."
    not_legal_certification: bool = True


class AuditSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "warn", "blocked"] = "ok"
    findings: int = Field(ge=0)
    risk_level: RiskScore = "LOW"
    summary: str = ""


__all__ = [
    "Action",
    "ALLOWED_CONTEXT_HITS",
    "AnalyzeRequest",
    "AnalyzeResponse",
    "AnalyzeSummary",
    "AuditCheck",
    "AuditResidual",
    "AuditResult",
    "AuditSummary",
    "BoundingBox",
    "ContentType",
    "ContextHit",
    "DetectedItem",
    "ErrorBody",
    "InternalFinding",
    "PIIType",
    "PublicFinding",
    "ProtectionSummary",
    "PublicFinding",
    "RedactRequest",
    "RedactResponse",
    "RedactionRule",
    "RiskScore",
    "SafeReceipt",
    "SessionRecord",
    "SESSION_TTL_SECONDS",
    "SESSION_TTL_SECONDS_DEMO",
    "ValidityClass",
    "ConfidenceBand",
    "QRStatus",
    "VerifyRequest",
    "VerifyResponse",
]
