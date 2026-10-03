"""
integration/test_audit.py – Integration tests for verify_cleaned_output
(Backend 3 – audit / verification layer).

Run from the repo root:
    pytest integration/test_audit.py -v

All test fixtures are SYNTHETIC.  No real Aadhaar, PAN, or financial data
is used anywhere in this file.
"""

from __future__ import annotations

import io
import struct
import sys
import zlib
from pathlib import Path

_SERVER_DIR = Path(__file__).parent.parent / "server"
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

from app.audit import AuditResult, CheckResult, ResidualHit  # noqa: E402
from app.verify_service import verify_cleaned_output  # noqa: E402

# ---------------------------------------------------------------------------
# PNG/JPEG fixture builders (all-synthetic, no real PII)
# ---------------------------------------------------------------------------


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    c = chunk_type + data
    return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)


def _minimal_png() -> bytes:
    """1×1 white PNG, no text chunks."""
    # IDAT: deflate stream for 1 pixel (RGB white)
    raw = b"\x00\xff\xff\xff"  # filter byte 0 + 1 pixel RGB
    compressed = zlib.compress(raw)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", compressed)
        + _png_chunk(b"IEND", b"")
    )


def _png_with_text_chunk(keyword: str, text: str) -> bytes:
    """PNG with a tEXt chunk carrying suspicious metadata."""
    payload = keyword.encode() + b"\x00" + text.encode()
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + _png_chunk(b"tEXt", payload)
        + _png_chunk(b"IDAT", zlib.compress(b"\x00\xff\xff\xff"))
        + _png_chunk(b"IEND", b"")
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEXT = "text"
_IMAGE = "image"


def _finding(
    fid: str,
    *,
    pii_type: str = "PAN",
    raw_value: str = "SYNTH-ABCDE1234F",
    value_masked: str = "SYNTH-ABCXXXX4F",
    action: str = "MASK",
    sensitivity: str | None = None,
    validity_class: str | None = None,
) -> dict:
    d: dict = {
        "id": fid,
        "type": pii_type,
        "raw_value": raw_value,
        "value_masked": value_masked,
        "action": action,
    }
    if sensitivity:
        d["sensitivity"] = sensitivity
    if validity_class:
        d["validity_class"] = validity_class
    return d


def _bytes(text: str) -> bytes:
    return text.encode("utf-8")


def _get_check(result: AuditResult, name: str) -> CheckResult:
    for check in result.checks:
        if check.name == name:
            return check
    raise AssertionError(
        f"Check '{name}' not found. Available: {[c.name for c in result.checks]}"
    )


# ---------------------------------------------------------------------------
# Section 1 – Clean result (text, no residual)
# ---------------------------------------------------------------------------


def test_clean_text_no_residual():
    """Cleaned text with no original strings → STRING_SEARCH PASSED."""
    result = verify_cleaned_output(
        original_session={},
        cleaned_bytes=_bytes("The document has been sanitized."),
        cleaned_content_type=_TEXT,
        findings=[_finding("f1", raw_value="SYNTH-ABCDE1234F")],
    )
    ss = _get_check(result, "STRING_SEARCH")
    assert ss.status == "PASSED"
    assert result.residuals == []
    # With pipeline stub DETECTOR_RESCAN is UNSUPPORTED → PARTIAL
    assert result.verdict in ("CLEAN", "PARTIAL")
    assert result.verdict != "FAIL"


def test_clean_text_empty_findings():
    """No findings → STRING_SEARCH PASSED, verdict not FAIL."""
    result = verify_cleaned_output(
        original_session={},
        cleaned_bytes=_bytes("Hello world"),
        cleaned_content_type=_TEXT,
        findings=[],
    )
    assert result.verdict in ("CLEAN", "PARTIAL")
    _get_check(result, "STRING_SEARCH").status == "PASSED"


def test_ran_count_is_correct():
    """ran must equal the number of PASSED or FAILED checks (not UNSUPPORTED)."""
    result = verify_cleaned_output(
        original_session={},
        cleaned_bytes=_bytes("clean text"),
        cleaned_content_type=_TEXT,
        findings=[],
    )
    expected_ran = sum(1 for c in result.checks if c.status in ("PASSED", "FAILED"))
    assert result.ran == expected_ran


def test_timestamp_present():
    """AuditResult must carry a non-empty ISO timestamp."""
    result = verify_cleaned_output(
        original_session={},
        cleaned_bytes=_bytes("ok"),
        cleaned_content_type=_TEXT,
        findings=[],
    )
    assert result.timestamp
    # Minimal format check: contains a T separator
    assert "T" in result.timestamp


# ---------------------------------------------------------------------------
# Section 2 – Residual value detected
# ---------------------------------------------------------------------------


def test_residual_value_causes_fail():
    """Cleaned text still contains the raw value → STRING_SEARCH FAILED, FAIL."""
    raw = "SYNTH-111122223333"
    result = verify_cleaned_output(
        original_session={},
        cleaned_bytes=_bytes(f"Data: {raw}"),
        cleaned_content_type=_TEXT,
        findings=[_finding("f1", pii_type="AADHAAR", raw_value=raw)],
    )
    assert result.verdict == "FAIL"
    assert _get_check(result, "STRING_SEARCH").status == "FAILED"
    assert len(result.residuals) == 1
    assert result.residuals[0].category == "AADHAAR"


def test_residual_hit_contains_no_raw_value():
    """ResidualHit.category and region must never contain the raw PII string."""
    raw = "SYNTH-9876543210987654"
    result = verify_cleaned_output(
        original_session={},
        cleaned_bytes=_bytes(f"Card: {raw}"),
        cleaned_content_type=_TEXT,
        findings=[_finding("f1", pii_type="CREDIT_CARD", raw_value=raw)],
    )
    assert result.verdict == "FAIL"
    for hit in result.residuals:
        assert raw not in (hit.category or "")
        assert raw not in (hit.region or "")


def test_kept_finding_is_still_reported_as_residual():
    """KEEP does not suppress raw-value detection or a residual report."""
    raw = "SYNTH-KEEPVAL-XYZ"
    result = verify_cleaned_output(
        original_session={},
        cleaned_bytes=_bytes(f"Retained: {raw}"),
        cleaned_content_type=_TEXT,
        findings=[_finding("f1", raw_value=raw, action="KEEP")],
    )
    assert _get_check(result, "STRING_SEARCH").status == "FAILED"
    assert result.verdict == "FAIL"
    assert result.residuals[0].category == "PAN"
    assert raw not in repr(result.to_dict())


def test_pdf_is_unsupported_and_never_clean():
    result = verify_cleaned_output(original_session={}, cleaned_bytes=b"%PDF-1.7",
                                   cleaned_content_type="pdf", findings=[])
    assert result.verdict == "PARTIAL"
    assert result.ran == 0


def test_empty_ocr_result_is_unsupported(monkeypatch):
    from app import ocr_engine
    monkeypatch.setattr(ocr_engine, "extract_text_and_boxes", lambda _image: [])
    result = verify_cleaned_output(original_session={"qr_codes": []},
                                   cleaned_bytes=_minimal_png(),
                                   cleaned_content_type=_IMAGE, findings=[])
    assert _get_check(result, "STRING_SEARCH").status == "UNSUPPORTED"
    assert result.verdict == "PARTIAL"


def test_multiple_findings_one_residual():
    """Two findings; one redacted, one present → FAIL with exactly one residual."""
    raw_present = "SYNTH-AADHAAR-111122223333"
    raw_gone = "SYNTH-PAN-ABCDE1234F"
    result = verify_cleaned_output(
        original_session={},
        cleaned_bytes=_bytes(f"Aadhaar still here: {raw_present}"),
        cleaned_content_type=_TEXT,
        findings=[
            _finding("f1", pii_type="PAN", raw_value=raw_gone),
            _finding("f2", pii_type="AADHAAR", raw_value=raw_present),
        ],
    )
    assert result.verdict == "FAIL"
    assert len(result.residuals) == 1
    assert result.residuals[0].category == "AADHAAR"


def test_region_from_bounding_box():
    """Finding with bounding_box → ResidualHit.region carries safe bbox string."""
    raw = "SYNTH-BBOX-VAL-XYZ"
    finding = {
        "id": "f1",
        "type": "PAN",
        "raw_value": raw,
        "action": "MASK",
        "bounding_box": {"x": 10, "y": 20, "w": 80, "h": 15},
    }
    result = verify_cleaned_output(
        original_session={},
        cleaned_bytes=_bytes(f"val: {raw}"),
        cleaned_content_type=_TEXT,
        findings=[finding],
    )
    assert result.verdict == "FAIL"
    hit = result.residuals[0]
    assert hit.region is not None
    assert "bbox" in hit.region
    assert raw not in hit.region


def test_region_from_span():
    """Finding with start/end → ResidualHit.region carries safe span string."""
    raw = "SYNTH-SPAN-VAL-XYZ"
    finding = {
        "id": "f1",
        "type": "PHONE",
        "raw_value": raw,
        "action": "MASK",
        "start": 5,
        "end": 23,
    }
    result = verify_cleaned_output(
        original_session={},
        cleaned_bytes=_bytes(f"val: {raw} end"),
        cleaned_content_type=_TEXT,
        findings=[finding],
    )
    assert result.verdict == "FAIL"
    hit = result.residuals[0]
    assert hit.region is not None
    assert "span" in hit.region
    assert raw not in hit.region


# ---------------------------------------------------------------------------
# Section 3 – UNSUPPORTED checks and PARTIAL verdict
# ---------------------------------------------------------------------------


def test_detector_rescan_unsupported_pipeline_stub():
    """pipeline.detect_pii_pipeline raises NotImplementedError → UNSUPPORTED."""
    result = verify_cleaned_output(
        original_session={},
        cleaned_bytes=_bytes("clean text"),
        cleaned_content_type=_TEXT,
        findings=[],
    )
    dr = _get_check(result, "DETECTOR_RESCAN")
    assert dr.status == "UNSUPPORTED"


def test_string_search_unsupported_for_image():
    """Image content → STRING_SEARCH UNSUPPORTED."""
    result = verify_cleaned_output(
        original_session={},
        cleaned_bytes=_minimal_png(),
        cleaned_content_type=_IMAGE,
        findings=[_finding("f1")],
    )
    ss = _get_check(result, "STRING_SEARCH")
    assert ss.status == "UNSUPPORTED"


def test_qr_redecode_not_applicable_for_text():
    """Plain text has no QR regions; format routing is an actual N/A check."""
    result = verify_cleaned_output(
        original_session={},
        cleaned_bytes=_bytes("some text"),
        cleaned_content_type=_TEXT,
        findings=[],
    )
    qr = _get_check(result, "QR_REDECODE")
    assert qr.status == "PASSED"
    assert "Not applicable" in qr.reason


def test_qr_redecode_runs_for_image():
    """For image content QR_REDECODE must run (PASSED or FAILED, not UNSUPPORTED)."""
    result = verify_cleaned_output(
        original_session={"qr_codes": []},
        cleaned_bytes=_minimal_png(),
        cleaned_content_type=_IMAGE,
        findings=[],
    )
    qr = _get_check(result, "QR_REDECODE")
    assert qr.status != "UNSUPPORTED", (
        f"QR_REDECODE should run for image but got UNSUPPORTED: {qr.reason}"
    )


def test_missing_original_image_session_makes_qr_check_unsupported():
    result = verify_cleaned_output(
        original_session=None,
        cleaned_bytes=_minimal_png(),
        cleaned_content_type=_IMAGE,
        findings=[],
    )
    assert _get_check(result, "QR_REDECODE").status == "UNSUPPORTED"
    assert result.verdict == "PARTIAL"


def test_partial_verdict_when_unsupported_checks_present():
    """No failures + some UNSUPPORTED → PARTIAL, never CLEAN."""
    result = verify_cleaned_output(
        original_session={},
        cleaned_bytes=_bytes("fully clean"),
        cleaned_content_type=_TEXT,
        findings=[],
    )
    # DETECTOR_RESCAN is UNSUPPORTED (pipeline stub) → verdict must be PARTIAL
    assert result.verdict == "PARTIAL"


def test_unsupported_never_causes_clean():
    """If any check is UNSUPPORTED the verdict must not be CLEAN."""
    result = verify_cleaned_output(
        original_session={},
        cleaned_bytes=_bytes("clean"),
        cleaned_content_type=_TEXT,
        findings=[],
    )
    statuses = {c.status for c in result.checks}
    if "UNSUPPORTED" in statuses:
        assert result.verdict != "CLEAN"


def test_missing_interfaces_reported():
    """missing_interfaces must name every stub that prevented a check."""
    result = verify_cleaned_output(
        original_session={},
        cleaned_bytes=_bytes("text"),
        cleaned_content_type=_TEXT,
        findings=[],
    )
    assert len(result.missing_interfaces) > 0
    assert any("pipeline" in iface for iface in result.missing_interfaces)


# ---------------------------------------------------------------------------
# Section 4 – No raw PII in any output field
# ---------------------------------------------------------------------------


def test_no_raw_pii_in_check_reasons():
    """Raw PII values must never appear in CheckResult.reason strings."""
    raw = "SYNTH-SECRET99887766"
    result = verify_cleaned_output(
        original_session={},
        cleaned_bytes=_bytes(f"Oops: {raw}"),
        cleaned_content_type=_TEXT,
        findings=[_finding("f1", raw_value=raw)],
    )
    for check in result.checks:
        assert raw not in check.reason, (
            f"Raw leaked into check '{check.name}' reason: {check.reason!r}"
        )


def test_no_raw_pii_in_notes():
    """Raw PII values must never appear in AuditResult.notes."""
    raw = "SYNTH-SECRETPAN1234X"
    result = verify_cleaned_output(
        original_session={},
        cleaned_bytes=_bytes(f"Value: {raw}"),
        cleaned_content_type=_TEXT,
        findings=[_finding("f1", raw_value=raw)],
    )
    combined_notes = " ".join(result.notes)
    assert raw not in combined_notes


def test_residual_hit_fields_are_safe():
    """ResidualHit must only carry category/page/region — never raw value."""
    raw = "SYNTH-RAWPII12345678"
    result = verify_cleaned_output(
        original_session={},
        cleaned_bytes=_bytes(f"Data: {raw}"),
        cleaned_content_type=_TEXT,
        findings=[_finding("f1", pii_type="PAN", raw_value=raw)],
    )
    assert result.verdict == "FAIL"
    for hit in result.residuals:
        assert hasattr(hit, "category")
        assert hasattr(hit, "page")
        assert hasattr(hit, "region")
        for val in (hit.category, str(hit.page), str(hit.region)):
            assert raw not in val


def test_result_shape():
    """AuditResult must have all required fields."""
    result = verify_cleaned_output(
        original_session={},
        cleaned_bytes=_bytes("ok"),
        cleaned_content_type=_TEXT,
        findings=[],
    )
    assert hasattr(result, "verdict")
    assert hasattr(result, "checks")
    assert hasattr(result, "residuals")
    assert hasattr(result, "notes")
    assert hasattr(result, "missing_interfaces")
    assert hasattr(result, "ran")
    assert hasattr(result, "timestamp")
    assert isinstance(result.checks, list)
    assert isinstance(result.residuals, list)
    assert isinstance(result.ran, int)


# ---------------------------------------------------------------------------
# Section 5 – Metadata inspection
# ---------------------------------------------------------------------------


def test_metadata_text_passes():
    """Text content → METADATA_INSPECT PASSED (no binary metadata)."""
    result = verify_cleaned_output(
        original_session={},
        cleaned_bytes=_bytes("plain text"),
        cleaned_content_type=_TEXT,
        findings=[],
    )
    assert _get_check(result, "METADATA_INSPECT").status == "PASSED"


def test_metadata_minimal_png_passes():
    """Minimal PNG with no text chunks → METADATA_INSPECT PASSED."""
    result = verify_cleaned_output(
        original_session={},
        cleaned_bytes=_minimal_png(),
        cleaned_content_type=_IMAGE,
        findings=[],
    )
    mi = _get_check(result, "METADATA_INSPECT")
    assert mi.status == "PASSED"


def test_metadata_png_with_text_chunk_fails():
    """PNG with tEXt chunk → METADATA_INSPECT FAILED."""
    png = _png_with_text_chunk("Comment", "Some embedded metadata text")
    result = verify_cleaned_output(
        original_session={},
        cleaned_bytes=png,
        cleaned_content_type=_IMAGE,
        findings=[],
    )
    mi = _get_check(result, "METADATA_INSPECT")
    assert mi.status == "FAILED"
    # Raw metadata text must not be in the reason verbatim (partial match is ok
    # for chunk-type names but raw content must not leak).
    assert "Some embedded metadata text" not in mi.reason


# ---------------------------------------------------------------------------
# Section 6 – QR re-decode (cv2)
# ---------------------------------------------------------------------------


def test_qr_redecode_no_qr_in_minimal_png():
    """Minimal PNG has no QR codes; original session empty → PASSED."""
    result = verify_cleaned_output(
        original_session={"qr_codes": []},
        cleaned_bytes=_minimal_png(),
        cleaned_content_type=_IMAGE,
        findings=[],
    )
    qr = _get_check(result, "QR_REDECODE")
    assert qr.status == "PASSED"
    assert result.verdict != "FAIL"


def test_qr_redecode_expected_redaction_disappearance_passes():
    """A QR selected for masking should disappear, not be treated as a leak."""
    result = verify_cleaned_output(
        original_session={"qr_codes": [{"data": "SYNTH", "points": [], "action": "MASK"}]},
        cleaned_bytes=_minimal_png(),
        cleaned_content_type=_IMAGE,
        findings=[],
    )
    qr = _get_check(result, "QR_REDECODE")
    assert qr.status == "PASSED"
    assert result.verdict != "FAIL"
    assert "SYNTH" not in repr(result.to_dict())


def test_qr_inventory_without_redaction_action_is_unsupported():
    result = verify_cleaned_output(
        original_session={"qr_codes": [{"data": "SYNTH-QR-PAYLOAD", "points": []}]},
        cleaned_bytes=_minimal_png(), cleaned_content_type=_IMAGE, findings=[])
    assert _get_check(result, "QR_REDECODE").status == "UNSUPPORTED"
    assert result.verdict == "PARTIAL"
    assert "SYNTH-QR-PAYLOAD" not in repr(result.to_dict())


def _patch_qr_detector(monkeypatch, fake_detector):
    import cv2
    monkeypatch.setattr(cv2, "QRCodeDetector", lambda: fake_detector)


def test_qr_multi_no_points_fallback_finds_remaining_masked_qr(monkeypatch):
    import numpy as np

    points = np.array([[[1, 1], [20, 1], [20, 20], [1, 20]]], dtype=float)

    class FakeDetector:
        def detectAndDecodeMulti(self, _image):
            return False, (), None, ()

        def detectAndDecode(self, _image):
            # Empty payload, but the returned rectangle proves a QR remains.
            return "", points[0], None

        def detectMulti(self, _image):
            return True, points

    _patch_qr_detector(monkeypatch, FakeDetector())
    payload = "SYNTHETIC-QR-SECRET"
    result = verify_cleaned_output(
        original_session={"qr_codes": [{"data": payload, "points": points[0].tolist(),
                                        "action": "MASK"}]},
        cleaned_bytes=_minimal_png(), cleaned_content_type=_IMAGE, findings=[])
    assert _get_check(result, "QR_REDECODE").status == "FAILED"
    assert any(hit.category == "QR" for hit in result.residuals)
    assert payload not in repr(result.to_dict())


def test_qr_fallback_unable_to_establish_absence_is_unsupported(monkeypatch):
    class FakeDetector:
        def detectAndDecodeMulti(self, _image):
            return False, (), None, ()

        def detectAndDecode(self, _image):
            raise RuntimeError("synthetic private payload must not escape")

        def detectMulti(self, _image):
            raise RuntimeError("synthetic private payload must not escape")

    _patch_qr_detector(monkeypatch, FakeDetector())
    result = verify_cleaned_output(
        original_session={"qr_codes": [{"data": "SYNTH", "points": [], "action": "MASK"}]},
        cleaned_bytes=_minimal_png(), cleaned_content_type=_IMAGE, findings=[])
    qr = _get_check(result, "QR_REDECODE")
    assert qr.status == "UNSUPPORTED"
    assert result.verdict == "PARTIAL"
    assert "synthetic private payload" not in repr(result.to_dict())


def test_qr_single_no_rectangle_but_rectangle_detector_error_is_unsupported(monkeypatch):
    class FakeDetector:
        def detectAndDecodeMulti(self, _image):
            return False, (), None, ()

        def detectAndDecode(self, _image):
            return "", None, None

        def detectMulti(self, _image):
            raise RuntimeError("synthetic private payload must not escape")

    _patch_qr_detector(monkeypatch, FakeDetector())
    payload = "SYNTH-MASKED-QR-SECRET"
    result = verify_cleaned_output(
        original_session={"qr_codes": [{"data": payload, "points": [],
                                        "action": "MASK"}]},
        cleaned_bytes=_minimal_png(), cleaned_content_type=_IMAGE, findings=[])
    qr = _get_check(result, "QR_REDECODE")
    assert qr.status == "UNSUPPORTED"
    assert result.verdict == "PARTIAL"
    assert "PASSED" not in repr(qr)
    assert payload not in repr(result.to_dict())
    assert "synthetic private payload" not in repr(result.to_dict())


def test_masked_qr_absence_passes_only_after_fallbacks_confirm_no_rectangles(monkeypatch):
    class FakeDetector:
        def detectAndDecodeMulti(self, _image):
            return False, (), None, ()

        def detectAndDecode(self, _image):
            return "", None, None

        def detectMulti(self, _image):
            return False, None

    _patch_qr_detector(monkeypatch, FakeDetector())
    result = verify_cleaned_output(
        original_session={"qr_codes": [{"data": "SYNTH", "points": [], "action": "REMOVE"}]},
        cleaned_bytes=_minimal_png(), cleaned_content_type=_IMAGE, findings=[])
    assert _get_check(result, "QR_REDECODE").status == "PASSED"


def test_kept_qr_is_unverified_and_never_clean(monkeypatch):
    import numpy as np

    points = np.array([[[1, 1], [20, 1], [20, 20], [1, 20]]], dtype=float)

    class FakeDetector:
        def detectAndDecodeMulti(self, _image):
            return True, ("SYNTH-PRIVATE-PAYLOAD",), points, ()

        def detectAndDecode(self, _image):
            raise AssertionError("fallback should not be needed when points exist")

        def detectMulti(self, _image):
            raise AssertionError("fallback should not be needed when points exist")

    _patch_qr_detector(monkeypatch, FakeDetector())
    payload = "SYNTH-PRIVATE-PAYLOAD"
    result = verify_cleaned_output(
        original_session={"qr_codes": [{"data": payload, "points": points[0].tolist(),
                                        "action": "KEEP"}]},
        cleaned_bytes=_minimal_png(), cleaned_content_type=_IMAGE, findings=[])
    qr = _get_check(result, "QR_REDECODE")
    assert qr.status == "UNSUPPORTED"
    assert "UNVERIFIED" in (qr.reason + qr.method_note).upper()
    assert result.verdict == "PARTIAL"
    assert payload not in repr(result.to_dict())


def test_qr_redecode_signature_unverified_note():
    """QR_REDECODE must note that signature/content is UNVERIFIED, not claimed."""
    result = verify_cleaned_output(
        original_session={"qr_codes": []},
        cleaned_bytes=_minimal_png(),
        cleaned_content_type=_IMAGE,
        findings=[],
    )
    qr = _get_check(result, "QR_REDECODE")
    # method_note or reason should indicate UNVERIFIED for authenticity
    combined = (qr.reason + qr.method_note).upper()
    assert "UNVERIFIED" in combined or "NOT VERIFIED" in combined or "DEFERRED" in combined


# ---------------------------------------------------------------------------
# Section 7 – Invalid / edge-case inputs
# ---------------------------------------------------------------------------


def test_unsupported_content_type_returns_partial():
    """PDF/other formats cannot silently pass or be represented as CLEAN."""
    result = verify_cleaned_output(
        original_session={},
        cleaned_bytes=b"anything",
        cleaned_content_type="video",
        findings=[],
    )
    assert result.verdict == "PARTIAL"
    assert result.ran == 0


def test_malformed_content_type_cannot_raise_or_pass():
    result = verify_cleaned_output(original_session={}, cleaned_bytes=b"bytes",
                                   cleaned_content_type=[], findings=[])
    assert result.verdict == "PARTIAL"


def test_empty_bytes_text_passes_string_search():
    """Empty bytes decoded as text; no match → STRING_SEARCH PASSED."""
    result = verify_cleaned_output(
        original_session={},
        cleaned_bytes=b"",
        cleaned_content_type=_TEXT,
        findings=[_finding("f1", raw_value="SYNTH-ABCDE1234F")],
    )
    assert _get_check(result, "STRING_SEARCH").status == "PASSED"


def test_malformed_finding_is_unsupported():
    """Malformed findings cannot be silently skipped into a passing check."""
    result = verify_cleaned_output(
        original_session={},
        cleaned_bytes=_bytes("clean"),
        cleaned_content_type=_TEXT,
        findings=["not-a-dict", None, 42],  # type: ignore[list-item]
    )
    assert _get_check(result, "STRING_SEARCH").status == "UNSUPPORTED"
    assert result.verdict == "PARTIAL"


def test_finding_without_raw_value_is_unsupported():
    """Missing original value makes the literal-search check unsupported."""
    result = verify_cleaned_output(
        original_session={},
        cleaned_bytes=_bytes("some text"),
        cleaned_content_type=_TEXT,
        findings=[{"id": "f1", "type": "PAN", "action": "MASK"}],
    )
    assert _get_check(result, "STRING_SEARCH").status == "UNSUPPORTED"


def test_method_note_present():
    """CheckResult.method_note must be non-empty for implemented checks."""
    result = verify_cleaned_output(
        original_session={},
        cleaned_bytes=_bytes("text"),
        cleaned_content_type=_TEXT,
        findings=[],
    )
    for check in result.checks:
        assert check.method_note, f"method_note empty for check '{check.name}'"
