"""
integration/test_gate.py – Integration tests for evaluate_export_gate (Backend 3).

Run from the repo root with:
    pytest integration/test_gate.py -v

The gate module lives at server/app/gate.py; we add server/ to sys.path so
that ``from app.gate import evaluate_export_gate`` resolves correctly without
installing the package.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make `server/` importable when pytest is invoked from the repo root.
_SERVER_DIR = Path(__file__).parent.parent / "server"
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

from app.gate import evaluate_export_gate  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _finding(
    fid: str,
    *,
    validity_class: str = "VALIDATED",
    sensitivity: str = "CONTACT",
) -> dict:
    return {"id": fid, "validity_class": validity_class, "sensitivity": sensitivity}


def _decision(
    fid: str,
    *,
    action: str = "MASK",
    decided_by_user: bool = True,
) -> dict:
    return {"id": fid, "action": action, "decided_by_user": decided_by_user}


# ---------------------------------------------------------------------------
# 1. Happy path: GOOD OCR + CLEAN audit → export allowed
# ---------------------------------------------------------------------------


def test_clean_audit_good_ocr_allows_export():
    result = evaluate_export_gate(
        findings=[_finding("f1", validity_class="VALIDATED", sensitivity="CONTACT")],
        decisions=[_decision("f1", action="MASK")],
        strict_mode=False,
        ocr_quality="GOOD",
        audit_verdict="CLEAN",
    )
    assert result["export_blocked"] is False
    assert result["block_reasons"] == []


def test_clean_audit_degraded_ocr_allows_export():
    """DEGRADED OCR is only blocked in strict mode if quality is UNREADABLE."""
    result = evaluate_export_gate(
        findings=[_finding("f1")],
        decisions=[_decision("f1")],
        strict_mode=False,
        ocr_quality="DEGRADED",
        audit_verdict="CLEAN",
    )
    assert result["export_blocked"] is False


def test_clean_strict_mode_good_ocr_validated_allows_export():
    """Strict mode with no problematic findings must still allow export."""
    result = evaluate_export_gate(
        findings=[_finding("f1", validity_class="VALIDATED", sensitivity="CONTACT")],
        decisions=[_decision("f1", action="MASK", decided_by_user=True)],
        strict_mode=True,
        ocr_quality="GOOD",
        audit_verdict="CLEAN",
    )
    assert result["export_blocked"] is False
    assert result["block_reasons"] == []


# ---------------------------------------------------------------------------
# 2. Audit verdict blocking
# ---------------------------------------------------------------------------


def test_partial_audit_blocks_export():
    result = evaluate_export_gate(
        findings=[],
        decisions=[],
        strict_mode=False,
        ocr_quality="GOOD",
        audit_verdict="PARTIAL",
    )
    assert result["export_blocked"] is True
    assert "BLOCK_AUDIT_NOT_CLEAN" in result["block_reasons"]


def test_fail_audit_blocks_export():
    result = evaluate_export_gate(
        findings=[],
        decisions=[],
        strict_mode=False,
        ocr_quality="GOOD",
        audit_verdict="FAIL",
    )
    assert result["export_blocked"] is True
    assert "BLOCK_AUDIT_NOT_CLEAN" in result["block_reasons"]


def test_unknown_audit_verdict_blocks_export():
    result = evaluate_export_gate(
        findings=[],
        decisions=[],
        strict_mode=False,
        ocr_quality="GOOD",
        audit_verdict="MAYBE",
    )
    assert result["export_blocked"] is True
    assert "ERR_UNKNOWN_AUDIT_VERDICT" in result["block_reasons"]


# ---------------------------------------------------------------------------
# 3. OCR quality checks
# ---------------------------------------------------------------------------


def test_unknown_ocr_quality_blocks_export():
    result = evaluate_export_gate(
        findings=[],
        decisions=[],
        strict_mode=False,
        ocr_quality="OK",          # old value; no longer accepted
        audit_verdict="CLEAN",
    )
    assert result["export_blocked"] is True
    assert "ERR_UNKNOWN_OCR_QUALITY" in result["block_reasons"]


def test_strict_unreadable_ocr_blocks_export():
    result = evaluate_export_gate(
        findings=[],
        decisions=[],
        strict_mode=True,
        ocr_quality="UNREADABLE",
        audit_verdict="CLEAN",
    )
    assert result["export_blocked"] is True
    assert "BLOCK_STRICT_UNREADABLE_OCR" in result["block_reasons"]


def test_non_strict_unreadable_ocr_does_not_block():
    """UNREADABLE OCR only triggers in strict mode."""
    result = evaluate_export_gate(
        findings=[],
        decisions=[],
        strict_mode=False,
        ocr_quality="UNREADABLE",
        audit_verdict="CLEAN",
    )
    assert result["export_blocked"] is False


# ---------------------------------------------------------------------------
# 4. REVIEW finding – undecided blocks, explicit resolution passes
# ---------------------------------------------------------------------------


def test_strict_undecided_review_finding_blocks():
    """REVIEW finding with no decision at all must block."""
    result = evaluate_export_gate(
        findings=[_finding("f1", validity_class="REVIEW", sensitivity="CONTACT")],
        decisions=[],                # no decision provided
        strict_mode=True,
        ocr_quality="GOOD",
        audit_verdict="CLEAN",
    )
    assert result["export_blocked"] is True
    assert "BLOCK_STRICT_UNRESOLVED_REVIEW" in result["block_reasons"]


def test_strict_review_with_system_default_decision_blocks():
    """decided_by_user=False must NOT satisfy the REVIEW resolution requirement."""
    result = evaluate_export_gate(
        findings=[_finding("f1", validity_class="REVIEW", sensitivity="CONTACT")],
        decisions=[_decision("f1", action="MASK", decided_by_user=False)],
        strict_mode=True,
        ocr_quality="GOOD",
        audit_verdict="CLEAN",
    )
    assert result["export_blocked"] is True
    assert "BLOCK_STRICT_UNRESOLVED_REVIEW" in result["block_reasons"]


def test_strict_review_truthy_string_decided_by_user_blocks():
    """decided_by_user='false' is truthy but is not the boolean True.
    The gate must use `is True` identity — not bool() — so this string
    must NOT resolve a REVIEW finding in strict mode."""
    result = evaluate_export_gate(
        findings=[_finding("f1", validity_class="REVIEW", sensitivity="CONTACT")],
        decisions=[{"id": "f1", "action": "MASK", "decided_by_user": "false"}],
        strict_mode=True,
        ocr_quality="GOOD",
        audit_verdict="CLEAN",
    )
    assert result["export_blocked"] is True
    assert "BLOCK_STRICT_UNRESOLVED_REVIEW" in result["block_reasons"]


def test_strict_review_explicitly_resolved_allows_export():
    """A REVIEW finding with decided_by_user=True must clear the block."""
    result = evaluate_export_gate(
        findings=[_finding("f1", validity_class="REVIEW", sensitivity="CONTACT")],
        decisions=[_decision("f1", action="MASK", decided_by_user=True)],
        strict_mode=True,
        ocr_quality="GOOD",
        audit_verdict="CLEAN",
    )
    assert result["export_blocked"] is False
    assert result["block_reasons"] == []


def test_non_strict_review_finding_does_not_block():
    """Outside strict mode, REVIEW findings are not grounds for blocking."""
    result = evaluate_export_gate(
        findings=[_finding("f1", validity_class="REVIEW", sensitivity="CONTACT")],
        decisions=[],
        strict_mode=False,
        ocr_quality="GOOD",
        audit_verdict="CLEAN",
    )
    assert result["export_blocked"] is False


# ---------------------------------------------------------------------------
# 5. High-risk KEEP – strict mode blocks, non-strict does not
# ---------------------------------------------------------------------------


def test_strict_high_risk_keep_govt_id_blocks():
    result = evaluate_export_gate(
        findings=[_finding("f1", validity_class="VALIDATED", sensitivity="GOVT_ID")],
        decisions=[_decision("f1", action="KEEP", decided_by_user=True)],
        strict_mode=True,
        ocr_quality="GOOD",
        audit_verdict="CLEAN",
    )
    assert result["export_blocked"] is True
    assert "BLOCK_STRICT_HIGH_RISK_KEEP" in result["block_reasons"]


def test_strict_high_risk_keep_financial_blocks():
    result = evaluate_export_gate(
        findings=[_finding("f1", validity_class="VALIDATED", sensitivity="FINANCIAL")],
        decisions=[_decision("f1", action="KEEP", decided_by_user=True)],
        strict_mode=True,
        ocr_quality="GOOD",
        audit_verdict="CLEAN",
    )
    assert result["export_blocked"] is True
    assert "BLOCK_STRICT_HIGH_RISK_KEEP" in result["block_reasons"]


def test_strict_high_risk_keep_health_blocks():
    result = evaluate_export_gate(
        findings=[_finding("f1", validity_class="VALIDATED", sensitivity="HEALTH")],
        decisions=[_decision("f1", action="KEEP", decided_by_user=True)],
        strict_mode=True,
        ocr_quality="GOOD",
        audit_verdict="CLEAN",
    )
    assert result["export_blocked"] is True
    assert "BLOCK_STRICT_HIGH_RISK_KEEP" in result["block_reasons"]


def test_strict_high_risk_keep_contact_blocks():
    result = evaluate_export_gate(
        findings=[_finding("f1", validity_class="VALIDATED", sensitivity="CONTACT")],
        decisions=[_decision("f1", action="KEEP", decided_by_user=True)],
        strict_mode=True,
        ocr_quality="GOOD",
        audit_verdict="CLEAN",
    )
    assert result["export_blocked"] is True
    assert "BLOCK_STRICT_HIGH_RISK_KEEP" in result["block_reasons"]


def test_mask_on_high_risk_finding_does_not_block():
    """MASK (not KEEP) on any valid high-risk finding must allow export."""
    result = evaluate_export_gate(
        findings=[_finding("f1", validity_class="VALIDATED", sensitivity="GOVT_ID")],
        decisions=[_decision("f1", action="MASK", decided_by_user=True)],
        strict_mode=True,
        ocr_quality="GOOD",
        audit_verdict="CLEAN",
    )
    assert result["export_blocked"] is False
    assert result["block_reasons"] == []


def test_non_strict_high_risk_keep_does_not_block():
    """High-risk KEEP is only blocked in strict mode."""
    result = evaluate_export_gate(
        findings=[_finding("f1", validity_class="VALIDATED", sensitivity="GOVT_ID")],
        decisions=[_decision("f1", action="KEEP", decided_by_user=True)],
        strict_mode=False,
        ocr_quality="GOOD",
        audit_verdict="CLEAN",
    )
    assert result["export_blocked"] is False


def test_keep_with_false_decided_by_user_blocks():
    """KEEP with decided_by_user=False must block; system cannot authorise KEEP."""
    result = evaluate_export_gate(
        findings=[_finding("f1", validity_class="VALIDATED", sensitivity="GOVT_ID")],
        decisions=[_decision("f1", action="KEEP", decided_by_user=False)],
        strict_mode=True,
        ocr_quality="GOOD",
        audit_verdict="CLEAN",
    )
    assert result["export_blocked"] is True
    assert "ERR_KEEP_WITHOUT_USER_DECISION" in result["block_reasons"]
    # The KEEP is rejected before it is evaluated as high-risk; the strict-mode
    # high-risk reason code is NOT emitted because decided_by_user is False.
    assert "BLOCK_STRICT_HIGH_RISK_KEEP" not in result["block_reasons"]


def test_keep_with_missing_decided_by_user_blocks():
    """KEEP with decided_by_user absent (key missing) must block."""
    result = evaluate_export_gate(
        findings=[_finding("f1", validity_class="VALIDATED", sensitivity="FINANCIAL")],
        decisions=[{"id": "f1", "action": "KEEP"}],   # no decided_by_user key
        strict_mode=False,
        ocr_quality="GOOD",
        audit_verdict="CLEAN",
    )
    assert result["export_blocked"] is True
    assert "ERR_KEEP_WITHOUT_USER_DECISION" in result["block_reasons"]


# ---------------------------------------------------------------------------
# 6. Expanded action set acceptance
# ---------------------------------------------------------------------------


def test_uidai_first8_action_accepted():
    result = evaluate_export_gate(
        findings=[_finding("f1")],
        decisions=[_decision("f1", action="UIDAI_FIRST8")],
        strict_mode=False,
        ocr_quality="GOOD",
        audit_verdict="CLEAN",
    )
    assert result["export_blocked"] is False
    assert not any("ERR_UNSUPPORTED_ACTION" in r for r in result["block_reasons"])


def test_replace_token_action_accepted():
    result = evaluate_export_gate(
        findings=[_finding("f1")],
        decisions=[_decision("f1", action="REPLACE_TOKEN")],
        strict_mode=False,
        ocr_quality="GOOD",
        audit_verdict="CLEAN",
    )
    assert result["export_blocked"] is False
    assert not any("ERR_UNSUPPORTED_ACTION" in r for r in result["block_reasons"])


def test_unknown_action_is_rejected():
    result = evaluate_export_gate(
        findings=[_finding("f1")],
        decisions=[_decision("f1", action="SCRAMBLE")],
        strict_mode=False,
        ocr_quality="GOOD",
        audit_verdict="CLEAN",
    )
    assert result["export_blocked"] is True
    assert "ERR_UNSUPPORTED_ACTION" in result["block_reasons"]


# ---------------------------------------------------------------------------
# 7. Input integrity: unknown IDs, duplicates, malformed entries
# ---------------------------------------------------------------------------


def test_duplicate_finding_id_blocks():
    findings = [
        _finding("f1", validity_class="VALIDATED"),
        _finding("f1", validity_class="FORMAT_ONLY"),   # duplicate
    ]
    result = evaluate_export_gate(
        findings=findings,
        decisions=[],
        strict_mode=False,
        ocr_quality="GOOD",
        audit_verdict="CLEAN",
    )
    assert result["export_blocked"] is True
    assert "ERR_DUPLICATE_FINDING_ID" in result["block_reasons"]


def test_duplicate_decision_id_blocks():
    result = evaluate_export_gate(
        findings=[_finding("f1")],
        decisions=[
            _decision("f1", action="MASK"),
            _decision("f1", action="REMOVE"),  # duplicate
        ],
        strict_mode=False,
        ocr_quality="GOOD",
        audit_verdict="CLEAN",
    )
    assert result["export_blocked"] is True
    assert "ERR_DUPLICATE_DECISION_ID" in result["block_reasons"]


def test_unknown_finding_id_in_decision_blocks():
    result = evaluate_export_gate(
        findings=[_finding("f1")],
        decisions=[_decision("f999", action="MASK")],   # f999 not in findings
        strict_mode=False,
        ocr_quality="GOOD",
        audit_verdict="CLEAN",
    )
    assert result["export_blocked"] is True
    assert "ERR_UNKNOWN_DECISION_ID" in result["block_reasons"]


def test_malformed_finding_blocks():
    result = evaluate_export_gate(
        findings=["not-a-dict"],  # type: ignore[list-item]
        decisions=[],
        strict_mode=False,
        ocr_quality="GOOD",
        audit_verdict="CLEAN",
    )
    assert result["export_blocked"] is True
    assert "ERR_MALFORMED_FINDING" in result["block_reasons"]


def test_malformed_decision_blocks():
    result = evaluate_export_gate(
        findings=[_finding("f1")],
        decisions=["not-a-dict"],  # type: ignore[list-item]
        strict_mode=False,
        ocr_quality="GOOD",
        audit_verdict="CLEAN",
    )
    assert result["export_blocked"] is True
    assert "ERR_MALFORMED_DECISION" in result["block_reasons"]


# ---------------------------------------------------------------------------
# 8. Result shape: only export_blocked and block_reasons are returned
# ---------------------------------------------------------------------------


def test_result_keys_are_exactly_two():
    result = evaluate_export_gate(
        findings=[],
        decisions=[],
        strict_mode=False,
        ocr_quality="GOOD",
        audit_verdict="CLEAN",
    )
    assert set(result.keys()) == {"export_blocked", "block_reasons"}


def test_result_never_contains_raw_values():
    """Smoke-check: inject a finding with a raw_value and ensure it does not
    appear anywhere in the returned reason codes."""
    finding_with_pii = {
        "id": "f1",
        "validity_class": "VALIDATED",
        "sensitivity": "GOVT_ID",
        "raw_value": "1234-5678-9012",   # must never leak
    }
    result = evaluate_export_gate(
        findings=[finding_with_pii],
        decisions=[_decision("f1", action="MASK")],
        strict_mode=True,
        ocr_quality="GOOD",
        audit_verdict="CLEAN",
    )
    combined = " ".join(result["block_reasons"])
    assert "1234-5678-9012" not in combined


# ---------------------------------------------------------------------------
# 9. Finding field validation: validity_class and sensitivity
# ---------------------------------------------------------------------------


def test_missing_validity_class_blocks():
    """A finding with no validity_class key must block."""
    finding_no_vc = {"id": "f1", "sensitivity": "CONTACT"}
    result = evaluate_export_gate(
        findings=[finding_no_vc],
        decisions=[],
        strict_mode=False,
        ocr_quality="GOOD",
        audit_verdict="CLEAN",
    )
    assert result["export_blocked"] is True
    assert "ERR_INVALID_VALIDITY_CLASS" in result["block_reasons"]


def test_unknown_validity_class_blocks():
    """A finding with an unrecognised validity_class must block."""
    result = evaluate_export_gate(
        findings=[{"id": "f1", "validity_class": "SUSPICIOUS", "sensitivity": "CONTACT"}],
        decisions=[],
        strict_mode=False,
        ocr_quality="GOOD",
        audit_verdict="CLEAN",
    )
    assert result["export_blocked"] is True
    assert "ERR_INVALID_VALIDITY_CLASS" in result["block_reasons"]


def test_missing_sensitivity_blocks():
    """A finding with no sensitivity key must block."""
    finding_no_sens = {"id": "f1", "validity_class": "VALIDATED"}
    result = evaluate_export_gate(
        findings=[finding_no_sens],
        decisions=[],
        strict_mode=False,
        ocr_quality="GOOD",
        audit_verdict="CLEAN",
    )
    assert result["export_blocked"] is True
    assert "ERR_INVALID_SENSITIVITY" in result["block_reasons"]


def test_unknown_sensitivity_blocks():
    """A finding with an unrecognised sensitivity value must block."""
    result = evaluate_export_gate(
        findings=[{"id": "f1", "validity_class": "VALIDATED", "sensitivity": "INTERNAL"}],
        decisions=[],
        strict_mode=False,
        ocr_quality="GOOD",
        audit_verdict="CLEAN",
    )
    assert result["export_blocked"] is True
    assert "ERR_INVALID_SENSITIVITY" in result["block_reasons"]


def test_both_fields_valid_allows_export():
    """Sanity: all four recognised sensitivities with VALIDATED class must pass."""
    for sens in ("GOVT_ID", "FINANCIAL", "HEALTH", "CONTACT"):
        result = evaluate_export_gate(
            findings=[_finding("f1", validity_class="VALIDATED", sensitivity=sens)],
            decisions=[_decision("f1", action="MASK")],
            strict_mode=False,
            ocr_quality="GOOD",
            audit_verdict="CLEAN",
        )
        assert result["export_blocked"] is False, f"Unexpected block for sensitivity={sens}"
