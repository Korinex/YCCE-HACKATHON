"""Fail-closed export gate for Backend 3.

Reason strings are fixed codes and never contain finding IDs or user data.
"""
from __future__ import annotations

from typing import Any

_AUDIT = {"CLEAN", "FAIL", "PARTIAL"}
_OCR = {"GOOD", "DEGRADED", "UNREADABLE"}
_VALIDITY = {"VALIDATED", "FORMAT_ONLY", "REVIEW"}
_SENSITIVITY = {"GOVT_ID", "FINANCIAL", "HEALTH", "CONTACT"}
_ACTIONS = {"MASK", "UIDAI_FIRST8", "REPLACE_TOKEN", "REMOVE", "KEEP"}


def evaluate_export_gate(*, findings: Any, decisions: Any, strict_mode: Any,
                         ocr_quality: Any, audit_verdict: Any) -> dict[str, Any]:
    """Return exactly export_blocked and safe, non-identifying block codes."""
    reasons: list[str] = []

    if not isinstance(audit_verdict, str) or audit_verdict not in _AUDIT:
        reasons.append("ERR_UNKNOWN_AUDIT_VERDICT")
    elif audit_verdict != "CLEAN":
        reasons.append("BLOCK_AUDIT_NOT_CLEAN")
    if not isinstance(ocr_quality, str) or ocr_quality not in _OCR:
        reasons.append("ERR_UNKNOWN_OCR_QUALITY")
    if type(strict_mode) is not bool:
        reasons.append("ERR_MALFORMED_STRICT_MODE")
        strict = True
    else:
        strict = strict_mode
    if strict and ocr_quality == "UNREADABLE":
        reasons.append("BLOCK_STRICT_UNREADABLE_OCR")

    if not isinstance(findings, (list, tuple)):
        reasons.append("ERR_MALFORMED_FINDINGS")
        findings = []
    if not isinstance(decisions, (list, tuple)):
        reasons.append("ERR_MALFORMED_DECISIONS")
        decisions = []

    by_id: dict[str, dict[str, Any]] = {}
    duplicate_findings = False
    for item in findings:
        if not isinstance(item, dict):
            reasons.append("ERR_MALFORMED_FINDING")
            continue
        fid = item.get("id")
        # Never echo IDs in output; even nominal IDs may contain user data.
        if not isinstance(fid, str) or not fid.strip():
            reasons.append("ERR_MISSING_FINDING_ID")
            continue
        if fid in by_id:
            duplicate_findings = True
        by_id[fid] = item
        if item.get("validity_class") not in _VALIDITY:
            reasons.append("ERR_INVALID_VALIDITY_CLASS")
        if item.get("sensitivity") not in _SENSITIVITY:
            reasons.append("ERR_INVALID_SENSITIVITY")
    if duplicate_findings:
        reasons.append("ERR_DUPLICATE_FINDING_ID")

    decisions_by_id: dict[str, dict[str, Any]] = {}
    duplicate_decisions = False
    for item in decisions:
        if not isinstance(item, dict):
            reasons.append("ERR_MALFORMED_DECISION")
            continue
        did, action = item.get("id"), item.get("action")
        if not isinstance(did, str) or not did.strip():
            reasons.append("ERR_MISSING_DECISION_ID")
            continue
        if action not in _ACTIONS:
            reasons.append("ERR_UNSUPPORTED_ACTION")
        if "decided_by_user" in item and type(item["decided_by_user"]) is not bool:
            reasons.append("ERR_MALFORMED_USER_DECISION")
        if action == "KEEP" and item.get("decided_by_user") is not True:
            reasons.append("ERR_KEEP_WITHOUT_USER_DECISION")
        if did in decisions_by_id:
            duplicate_decisions = True
        decisions_by_id[did] = item
    if duplicate_decisions:
        reasons.append("ERR_DUPLICATE_DECISION_ID")
    if any(did not in by_id for did in decisions_by_id):
        reasons.append("ERR_UNKNOWN_DECISION_ID")

    if strict:
        for fid, finding in by_id.items():
            decision = decisions_by_id.get(fid, {})
            explicit = decision.get("decided_by_user") is True
            if finding.get("validity_class") == "REVIEW" and not explicit:
                reasons.append("BLOCK_STRICT_UNRESOLVED_REVIEW")
            if (decision.get("action") == "KEEP" and explicit
                    and finding.get("sensitivity") in _SENSITIVITY):
                reasons.append("BLOCK_STRICT_HIGH_RISK_KEEP")

    # Deterministic de-duplication, with no caller-provided content in reasons.
    unique = list(dict.fromkeys(reasons))
    return {"export_blocked": bool(unique), "block_reasons": unique}
