"""Typed server-side session contract and raw-value-safe API finding adapter.

Backend 1 owns route/session lifecycle wiring. This module defines the handoff
shape: keep ``SessionRecord`` in the process-local cache, pass it intact to the
proof service, and use ``finding_for_api`` for any client-visible finding.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, TypedDict


class FindingDecision(TypedDict):
    id: str
    action: Literal["MASK", "REMOVE", "KEEP", "UIDAI_FIRST8", "REPLACE_TOKEN"]
    decided_by_user: bool


class OCRToken(TypedDict):
    text: str
    confidence: float
    bounding_box: dict[str, int]
    engine: str
    start: int
    end: int


class QRFinding(TypedDict):
    id: str
    decoded: bool
    validation_status: Literal["VERIFIED_FOR_THIS_ARTIFACT", "UNVERIFIED", "UNSUPPORTED_AT_CARD"]
    fields: list[dict[str, Any]]
    quiet_zone_box: dict[str, int]
    raw_payload_returned: bool


class InternalFinding(TypedDict):
    """Complete finding kept server-side; ``raw_value`` must never cross the API."""

    id: str
    type: str
    raw_value: str
    value_masked: str
    is_valid: bool
    validation_method: str
    validation_reason: str
    validation_tier: Literal["VALIDATED", "FORMAT_ONLY", "REVIEW"]
    confidence: float
    confidence_band: Literal["HIGH", "MEDIUM", "LOW"]
    start: int | None
    end: int | None
    bounding_box: dict[str, int] | None
    action: str
    rule: str
    context_hit: list[str]
    sensitivity: str
    source: Literal["text", "ocr", "qr"]
    ocr_confidence: float | None
    page: int | None
    review_required: bool


class SessionRecord(TypedDict):
    """Exact verification input retained in memory for the active workflow.

    ``original_content`` is the original UTF-8 text or original file bytes, never
    client-supplied findings. ``findings`` are Backend 2's complete internal
    findings. ``decisions`` are validated against those finding IDs before proof.
    """

    request_id: str
    content_type: Literal["text", "image", "pdf"]
    original_content: str | bytes
    findings: list[InternalFinding]
    decisions: list[FindingDecision]
    ocr_tokens: list[OCRToken]
    qr_findings: list[QRFinding]
    document: dict[str, Any]
    created_at: datetime
    expires_at: datetime


class VerificationInput(TypedDict):
    session: SessionRecord
    cleaned_content: str | bytes


# Backend 3 implementation contract:
# verify_cleaned_output(session: SessionRecord,
#                       cleaned_content: str | bytes) -> AuditResult
# `session` is the complete retained record below; `cleaned_content` is the
# just-rendered artifact. The returned audit must not echo any raw_value.


class PublicFinding(TypedDict):
    """Feature-guide finding contract returned to the UI; contains no raw value."""

    id: str
    type: str
    raw_masked: str
    validity_class: str
    confidence: float
    confidence_band: str
    rule: str
    reason: str
    context_hit: list[str]
    sensitivity: str
    source: str
    ocr_confidence: float | None
    page: int | None
    bbox: dict[str, int | str] | None
    default_action: str
    decided: bool


_RULE_FALLBACK = {
    "AADHAAR": "aadhaar.verhoeff.v1", "PAN": "pan.format.v1", "PHONE": "phone.india.v1",
    "BANK_ACCOUNT": "bank_account.context.v1", "IFSC": "ifsc.format.v1", "UPI": "upi.suffix.v1",
    "CREDIT_CARD": "card.luhn.v1", "EMAIL": "email.format.v1", "HEALTH_TERM": "health.lexicon.v1",
}


def finding_for_api(finding: InternalFinding) -> PublicFinding:
    """Whitelist safe fields and deliberately discard internal ``raw_value``."""
    finding_id = str(finding["id"])
    masked = str(finding.get("value_masked") or "[REDACTED]")
    if finding.get("raw_value") and finding["raw_value"] in masked:
        masked = "[REDACTED]"
    raw_masked = f"{masked} | {finding_id}"
    source = finding.get("source", "text")
    box = finding.get("bounding_box")
    bbox = None
    if box is not None:
        bbox = {key: int(box[key]) for key in ("x", "y", "w", "h")}
        bbox["space"] = "pixels"
    return {
        "id": finding_id,
        "type": str(finding["type"]),
        "raw_masked": raw_masked,
        "validity_class": str(finding.get("validation_tier", "REVIEW")),
        "confidence": float(finding.get("confidence", 0.0)),
        "confidence_band": str(finding.get("confidence_band", "LOW")),
        "rule": str(finding.get("rule") or _RULE_FALLBACK.get(finding["type"], "scout.pattern.v1")),
        "reason": str(finding.get("validation_reason", "Human review required")),
        "context_hit": [str(hit) for hit in finding.get("context_hit", [])],
        "sensitivity": str(finding.get("sensitivity", "OTHER")),
        "source": str(source),
        "ocr_confidence": finding.get("ocr_confidence"),
        "page": finding.get("page"),
        "bbox": bbox,
        "default_action": str(finding.get("action", "MASK")),
        "decided": False,
    }


def findings_for_api(findings: list[InternalFinding]) -> list[PublicFinding]:
    """Adapt a set of internal findings without serializing raw values."""
    return [finding_for_api(finding) for finding in findings]


def apply_decisions_to_api_findings(
    findings: list[PublicFinding], decisions: list[FindingDecision]
) -> list[PublicFinding]:
    """Return presentation copies marked decided; never use this for redaction."""
    decided_ids = {decision["id"] for decision in decisions if decision.get("decided_by_user")}
    return [{**finding, "decided": finding["id"] in decided_ids} for finding in findings]
