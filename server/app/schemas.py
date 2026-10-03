from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

PIIType = Literal[
    "AADHAAR", "PAN", "PHONE", "BANK_ACCOUNT", "IFSC", "UPI", "CREDIT_CARD"
]
Action = Literal["MASK", "REMOVE", "KEEP"]
RiskScore = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
ContentType = Literal["text", "image"]


class BoundingBox(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    w: int = Field(ge=0)
    h: int = Field(ge=0)


class DetectedItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: PIIType
    raw_value: str
    value_masked: str
    is_valid: bool
    validation_method: str
    validation_reason: str
    confidence: float = Field(ge=0, le=1)
    start: int | None = Field(default=None, ge=0)
    end: int | None = Field(default=None, ge=0)
    bounding_box: BoundingBox | None = None
    action: Action = "MASK"


class AnalyzeSummary(BaseModel):
    total_pii_found: int = Field(ge=0)
    validated_pii_count: int = Field(ge=0)
    risk_score: RiskScore
    breakdown: dict[str, int] = Field(default_factory=dict)


class AnalyzeResponse(BaseModel):
    status: Literal["success"] = "success"
    request_id: str
    content_type: ContentType
    extracted_text: str | None = None
    detected_items: list[DetectedItem] = Field(default_factory=list)
    summary: AnalyzeSummary
    warnings: list[str] = Field(default_factory=list)


class RedactionRule(BaseModel):
    id: str
    action: Action


class RedactRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    content_type: ContentType
    text: str | None = None
    file_b64: str | None = None
    detected_items: list[DetectedItem] = Field(default_factory=list)
    redaction_rules: list[RedactionRule] = Field(default_factory=list)


class ProtectionSummary(BaseModel):
    protected_records_count: int = Field(ge=0)
    breakdown: dict[str, int] = Field(default_factory=dict)
    status: Literal["SECURED"] = "SECURED"


class RedactResponse(BaseModel):
    status: Literal["success"] = "success"
    sanitized_text: str | None = None
    sanitized_file_b64: str | None = None
    download_filename: str
    protection_summary: ProtectionSummary


class ErrorBody(BaseModel):
    status: Literal["error"] = "error"
    error: dict[str, Any]
