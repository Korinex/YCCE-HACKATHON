"""Synthetic Backend 3 break matrix; no real identity or banking documents."""
from __future__ import annotations

import sys
from pathlib import Path

SERVER_DIR = Path(__file__).parent.parent / "server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from app.gate import evaluate_export_gate
from app.verify_service import verify_cleaned_output


def _finding() -> dict:
    return {"id": "safe_test_1", "validity_class": "VALIDATED",
            "sensitivity": "CONTACT", "type": "PHONE",
            "raw_value": "555-0100", "action": "MASK"}


def test_residual_synthetic_value_fails_audit():
    audit = verify_cleaned_output(original_session={},
                                  cleaned_bytes=b"contact 555-0100",
                                  cleaned_content_type="text", findings=[_finding()])
    assert audit.verdict == "FAIL"
    gate = evaluate_export_gate(findings=[_finding()], decisions=[], strict_mode=False,
                                ocr_quality="GOOD", audit_verdict=audit.verdict)
    assert gate["export_blocked"] is True


def test_partial_audit_and_unreadable_ocr_block_export():
    result = evaluate_export_gate(findings=[_finding()], decisions=[], strict_mode=True,
                                  ocr_quality="UNREADABLE", audit_verdict="PARTIAL")
    assert result["export_blocked"] is True
    assert "BLOCK_AUDIT_NOT_CLEAN" in result["block_reasons"]
    assert "BLOCK_STRICT_UNREADABLE_OCR" in result["block_reasons"]


def test_review_requires_explicit_resolution_in_strict_mode():
    finding = {**_finding(), "validity_class": "REVIEW"}
    unresolved = evaluate_export_gate(findings=[finding], decisions=[], strict_mode=True,
                                      ocr_quality="GOOD", audit_verdict="CLEAN")
    resolved = evaluate_export_gate(
        findings=[finding], decisions=[{"id": "safe_test_1", "action": "MASK",
                                        "decided_by_user": True}], strict_mode=True,
        ocr_quality="GOOD", audit_verdict="CLEAN")
    assert unresolved["export_blocked"] is True
    assert resolved["export_blocked"] is False
