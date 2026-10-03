"""
verify_service.py – Cleaned-output verification for the PS-06 Privacy Shield
(Backend 3).

Public surface
--------------
verify_cleaned_output(
    *,
    original_session,
    cleaned_bytes: bytes,
    cleaned_content_type: str,
    findings,
) -> AuditResult

Design constraints
------------------
* Fail-closed: any unexpected exception inside a check marks that check FAILED.
  Only genuine "interface not yet implemented" (NotImplementedError from the
  intelligence-track stubs) becomes UNSUPPORTED.
* No new dependencies: only Python stdlib + opencv-python and Pillow, which are
  already installed (requirements.txt and confirmed by pip list).
* Never stores or surfaces raw PII values anywhere.  ResidualHit carries only
  category, page, and region.  Check reasons and notes never echo raw values.
* Unsupported checks count as PARTIAL, not CLEAN.

Checks performed
----------------
1. DETECTOR_RESCAN  – Re-runs pipeline.detect_pii_pipeline.
                      UNSUPPORTED until intelligence track merges (stub raises
                      NotImplementedError).

2. STRING_SEARCH    – Literal search for every original matched value in the
                      cleaned text.  Text only; image → UNSUPPORTED.
                      Implemented: stdlib re.  Fail-closed.

3. METADATA_INSPECT – Inspects EXIF metadata via Pillow (images) and ZIP
                      container docProps via stdlib zipfile (docx/xlsx/odt).
                      Text → trivially PASSED.  Implemented: Pillow + stdlib.

4. QR_REDECODE      – Re-decodes QR codes via cv2.QRCodeDetector (installed)
                      and compares bounding polygons with the original session.
                      Image only; text → UNSUPPORTED.
                      QR signature verification is intentionally deferred;
                      authenticity is NOT claimed — result is UNVERIFIED/PASSED
                      when shapes match.
                      Implemented: opencv-python cv2.QRCodeDetector.

Verdict logic
-------------
* Any FAILED check   → FAIL.
* Any UNSUPPORTED check (all supported passed) → PARTIAL.
* All checks PASSED (none unsupported) → CLEAN.

Field compatibility (Backend 2 bridge)
---------------------------------------
Backend 2 may supply DetectedItem dicts with these fields:
  raw_value, value_masked, start, end, bounding_box (dict x/y/w/h), type,
  action, is_valid, validation_method, validation_reason, confidence.
Backend 3 spec refers to: raw_value, validity_class, raw_span, bbox,
  sensitivity, page.
Mapping applied (read-only, safe, within Backend 3 only):
  type      → category (for ResidualHit)
  raw_value → search needle (transient; never stored in result)
  bounding_box → region descriptor string
  start/end → raw_span equivalent
  sensitivity / validity_class → used if present; absent → PARTIAL noted.

Missing interfaces (Backend 1 / intelligence track)
----------------------------------------------------
pipeline.detect_pii_pipeline      – DETECTOR_RESCAN → UNSUPPORTED
ocr_engine.extract_text_and_boxes – NOT called; cv2 used directly for QR.
"""

from __future__ import annotations

import io
import re
import struct
import zipfile
from typing import Any

from .audit import AuditResult, CheckResult, ResidualHit

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MISSING_PIPELINE = "pipeline.detect_pii_pipeline"

# Minimum printable-char count in a JPEG APP segment to be considered suspicious.
_JPEG_APP_PRINTABLE_THRESHOLD = 8

# Minimum text length in a ZIP docProps entry to be considered suspicious.
_ZIP_DOCPROPS_TEXT_THRESHOLD = 4


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_decode(data: bytes) -> str:
    """Best-effort UTF-8 decode of bytes; replace undecodable bytes."""
    return data.decode("utf-8", errors="replace")


def _category_from_finding(finding: dict[str, Any]) -> str:
    """Extract a safe PII category label from a finding dict.

    Tries Backend-2 field ``type``, then Backend-3 field ``sensitivity``,
    then falls back to ``"UNKNOWN"``.  Never returns a raw value.
    """
    candidate = finding.get("type") or finding.get("sensitivity")
    allowed = {"AADHAAR", "VID", "PAN", "PHONE", "BANK_ACCOUNT", "IFSC",
               "UPI", "CREDIT_CARD", "GSTIN", "PASSPORT", "VOTER_ID",
               "DRIVING_LICENCE", "VEHICLE", "EMAIL", "HEALTH_TERM",
               "GOVT_ID", "FINANCIAL", "HEALTH", "CONTACT"}
    return candidate if isinstance(candidate, str) and candidate in allowed else "UNKNOWN"


def _region_from_finding(finding: dict[str, Any]) -> str | None:
    """Build a safe spatial descriptor from bounding_box or start/end.

    Never includes raw PII values.
    """
    bb = finding.get("bounding_box") or finding.get("bbox")
    if isinstance(bb, dict):
        x = bb.get("x", 0)
        y = bb.get("y", 0)
        w = bb.get("w", 0)
        h = bb.get("h", 0)
        if any(type(value) is not int or value < 0 for value in (x, y, w, h)):
            return None
        return f"bbox:x={x},y={y},w={w},h={h}"
    start = finding.get("start") or finding.get("raw_span_start")
    end = finding.get("end") or finding.get("raw_span_end")
    if start is not None and end is not None:
        if type(start) is not int or type(end) is not int or start < 0 or end < start:
            return None
        return f"span:{start}-{end}"
    return None


# ---------------------------------------------------------------------------
# Check 1 – Detector re-scan
# ---------------------------------------------------------------------------


def _check_detector_rescan(
    cleaned_bytes: bytes,
    cleaned_content_type: str,
    missing_interfaces: list[str],
) -> CheckResult:
    """Attempt to re-run the PII detection pipeline over the cleaned output.

    UNSUPPORTED when pipeline.detect_pii_pipeline raises NotImplementedError
    (intelligence track stub not yet merged).
    """
    try:
        from .pipeline import detect_pii_pipeline  # noqa: PLC0415

        if cleaned_content_type == "text":
            text = _safe_decode(cleaned_bytes)
            hits = detect_pii_pipeline(text=text)
        else:
            hits = detect_pii_pipeline(image_bytes=cleaned_bytes)

        if hits:
            return CheckResult(
                name="DETECTOR_RESCAN",
                status="FAILED",
                reason=f"{len(hits)} PII item(s) detected in cleaned output",
                method_note="pipeline.detect_pii_pipeline",
            )
        return CheckResult(
            name="DETECTOR_RESCAN",
            status="PASSED",
            method_note="pipeline.detect_pii_pipeline",
        )

    except NotImplementedError:
        missing_interfaces.append(_MISSING_PIPELINE)
        return CheckResult(
            name="DETECTOR_RESCAN",
            status="UNSUPPORTED",
            reason="pipeline.detect_pii_pipeline not yet implemented (intelligence track stub)",
            method_note="stub: intelligence track",
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            name="DETECTOR_RESCAN",
            status="FAILED",
            reason=f"Unexpected error during detector re-scan: {type(exc).__name__}",
            method_note="pipeline.detect_pii_pipeline (error)",
        )


# ---------------------------------------------------------------------------
# Check 2 – String search
# ---------------------------------------------------------------------------


def _check_string_search(
    cleaned_bytes: bytes,
    cleaned_content_type: str,
    findings: list[dict[str, Any]],
) -> tuple[CheckResult, list[ResidualHit]]:
    """Search the cleaned text for every original matched string.

    Works for text content only.  For image content we cannot extract text
    without OCR, so the check is UNSUPPORTED.

    A finding is searched only when:
    - It is a dict with a non-trivial raw_value or value_masked.
    - Its action is not KEEP (intentionally retained).

    The raw value is used transiently as a search needle and is NEVER stored
    in any result field, log, or exception message.
    """
    if cleaned_content_type == "text":
        cleaned_text = _safe_decode(cleaned_bytes)
    elif cleaned_content_type == "image":
        try:
            from .ocr_engine import extract_text_and_boxes
            tokens = extract_text_and_boxes(cleaned_bytes)
            cleaned_text = " ".join(str(token.get("text", "")) for token in tokens
                                    if isinstance(token, dict))
        except NotImplementedError:
            return (CheckResult(name="STRING_SEARCH", status="UNSUPPORTED",
                                reason="OCR interface unavailable for cleaned image",
                                method_note="ocr_engine.extract_text_and_boxes"), [])
        except Exception as exc:  # noqa: BLE001
            return (CheckResult(name="STRING_SEARCH", status="FAILED",
                                reason=f"OCR search failed: {type(exc).__name__}",
                                method_note="ocr_engine.extract_text_and_boxes"), [])
    else:
        return (CheckResult(name="STRING_SEARCH", status="UNSUPPORTED",
                            reason="Unsupported content type", method_note="none"), [])
    residuals: list[ResidualHit] = []

    for finding in findings:
        if not isinstance(finding, dict):
            continue
        action = finding.get("action", "MASK")
        if action == "KEEP":
            continue  # intentionally retained; not a residual

        # Prefer raw_value for accurate matching.  value_masked is a fallback
        # but only if it doesn't contain placeholder X sequences (which would
        # produce false positives on token patterns).
        raw = finding.get("raw_value", "") or ""
        masked = finding.get("value_masked", "") or ""

        search_value: str | None = None
        if isinstance(raw, str) and raw:
            search_value = raw  # transient; never stored
        elif isinstance(masked, str) and masked and "X" not in masked:
            search_value = masked
        elif raw or masked:
            return (CheckResult(name="STRING_SEARCH", status="UNSUPPORTED",
                                reason="Finding search value malformed",
                                method_note="in-memory literal search"), residuals)

        if not search_value:
            continue

        pattern = re.escape(search_value)
        if re.search(pattern, cleaned_text):
            residuals.append(
                ResidualHit(
                    category=_category_from_finding(finding),
                    page=None,
                    region=_region_from_finding(finding),
                )
            )

    if residuals:
        return (
            CheckResult(
                name="STRING_SEARCH",
                status="FAILED",
                reason=f"{len(residuals)} original matched string(s) still present in cleaned text",
                method_note="stdlib re.escape + re.search",
            ),
            residuals,
        )

    return (
        CheckResult(
            name="STRING_SEARCH",
            status="PASSED",
            method_note="stdlib re.escape + re.search",
        ),
        [],
    )


# ---------------------------------------------------------------------------
# Check 3 – Metadata inspection
# ---------------------------------------------------------------------------


def _check_metadata_inspect(
    cleaned_bytes: bytes,
    cleaned_content_type: str,
) -> CheckResult:
    """Inspect binary metadata for suspicious embedded text.

    For images: uses Pillow (already installed) for EXIF/XMP extraction, and
    falls back to raw struct-based chunk scanning for PNG tEXt/iTXt/zTXt.
    For ZIP-based containers (docx/xlsx/odt): inspects ZIP comment and
    docProps/core.xml using stdlib zipfile.
    For plain text: trivially PASSED (no binary metadata to inspect).

    This is a heuristic check.  Metadata presence does not guarantee PII, but
    unexpected metadata in a supposedly cleaned file is flagged.
    """
    if cleaned_content_type == "text":
        return CheckResult(
            name="METADATA_INSPECT",
            status="PASSED",
            reason="Text content has no binary metadata to inspect",
            method_note="content-type routing",
        )

    suspicious_fields: list[str] = []
    data = cleaned_bytes

    if cleaned_content_type == "image" and not (
        data.startswith(b"\xff\xd8")
        or data.startswith(b"\x89PNG\r\n\x1a\n")
        or data.startswith(b"PK\x03\x04")
    ):
        return CheckResult(name="METADATA_INSPECT", status="UNSUPPORTED",
                           reason="Image format is not supported by metadata inspectors",
                           method_note="Pillow/PNG/ZIP format detection")

    try:
        # ── Pillow EXIF for JPEG and PNG ─────────────────────────────────────
        if data[:2] == b"\xff\xd8" or data[:8] == b"\x89PNG\r\n\x1a\n":
            try:
                from PIL import Image  # noqa: PLC0415
                with Image.open(io.BytesIO(data)) as img:
                    exif_data = img.getexif()
                    if exif_data:
                        # Count non-trivial EXIF tags with printable string values.
                        non_empty = [
                            v for v in exif_data.values()
                            if isinstance(v, (str, bytes))
                            and len(str(v).strip()) > 2
                        ]
                        if non_empty:
                            suspicious_fields.append(
                                f"EXIF metadata: {len(non_empty)} non-empty tag(s)"
                            )
                    # Also check XMP via info dict if available.
                    info = img.info or {}
                    for key in ("xmp", "XML:com.adobe.xmp", "comment"):
                        val = info.get(key)
                        if val and len(str(val).strip()) > 4:
                            suspicious_fields.append(
                                f"Image info key '{key}': non-empty ({len(str(val))} chars)"
                            )
            except Exception:  # noqa: BLE001
                pass  # fall through to raw struct scan below

        # ── Raw PNG chunk scan (tEXt / iTXt / zTXt) ─────────────────────────
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            pos = 8
            while pos + 12 <= len(data):
                length = struct.unpack(">I", data[pos : pos + 4])[0]
                chunk_type = data[pos + 4 : pos + 8]
                chunk_data = data[pos + 8 : pos + 8 + length]
                if chunk_type in (b"tEXt", b"iTXt", b"zTXt"):
                    payload_parts = chunk_data.split(b"\x00", 1)
                    if len(payload_parts) > 1 and payload_parts[1].strip():
                        tag = chunk_type.decode("ascii", errors="replace")
                        suspicious_fields.append(
                            f"PNG {tag} chunk: non-empty text metadata"
                        )
                pos += 12 + length

        # ── Raw JPEG APP segment scan (fallback) ────────────────────────────
        elif data[:2] == b"\xff\xd8":
            pos = 2
            while pos + 4 <= len(data):
                if data[pos] != 0xFF:
                    break
                marker = data[pos + 1]
                seg_len = struct.unpack(">H", data[pos + 2 : pos + 4])[0]
                if marker in (0xE1, 0xEC, 0xED):
                    payload = data[pos + 4 : pos + 2 + seg_len]
                    printable = payload.decode("latin-1", errors="replace")
                    readable = "".join(c for c in printable if c.isprintable())
                    if len(readable) > _JPEG_APP_PRINTABLE_THRESHOLD:
                        suspicious_fields.append(
                            f"JPEG APP{marker - 0xE0} segment: {len(readable)} printable chars"
                        )
                pos += 2 + seg_len

        # ── ZIP-based container (docx / xlsx / odt) ──────────────────────────
        elif data[:4] == b"PK\x03\x04":
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                comment = zf.comment
                if comment and comment.strip():
                    suspicious_fields.append("ZIP comment field is non-empty")
                for name in zf.namelist():
                    if "docProps" in name and name.endswith(".xml"):
                        xml_bytes = zf.read(name)
                        text = re.sub(rb"<[^>]+>", b"", xml_bytes)
                        text_str = text.decode("utf-8", errors="replace").strip()
                        if len(text_str) > _ZIP_DOCPROPS_TEXT_THRESHOLD:
                            suspicious_fields.append(
                                f"ZIP docProps metadata is non-empty ({len(text_str)} chars)"
                            )

    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            name="METADATA_INSPECT",
            status="FAILED",
            reason=f"Metadata parsing error: {type(exc).__name__}",
            method_note="Pillow EXIF + struct + zipfile (error)",
        )

    # Deduplicate to avoid double-reporting from Pillow + raw scan overlap.
    seen: set[str] = set()
    unique_suspicious = [f for f in suspicious_fields if not (f in seen or seen.add(f))]  # type: ignore[func-returns-value]

    if unique_suspicious:
        summary = "; ".join(unique_suspicious[:5])
        return CheckResult(
            name="METADATA_INSPECT",
            status="FAILED",
            reason=f"Suspicious metadata found: {summary}",
            method_note="Pillow EXIF + struct chunk scan + zipfile",
        )

    return CheckResult(
        name="METADATA_INSPECT",
        status="PASSED",
        method_note="Pillow EXIF + struct chunk scan + zipfile",
    )


# ---------------------------------------------------------------------------
# Check 4 – QR re-decode / rectangle comparison
# ---------------------------------------------------------------------------


def _check_qr_redecode(
    cleaned_bytes: bytes,
    cleaned_content_type: str,
    original_session: Any,
) -> CheckResult:
    """Re-decode QR codes using cv2.QRCodeDetector and compare with original.

    cv2 (opencv-python 5.0) is already installed; this check is therefore
    fully implemented for image content.

    QR SIGNATURE VERIFICATION IS INTENTIONALLY DEFERRED.
    This check only verifies that the number and approximate bounding polygons
    of QR codes in the cleaned image match those recorded in the original
    session.  It does NOT claim to verify QR content authenticity.

    Result is UNVERIFIED/PASSED when shapes match (not a security guarantee),
    FAILED when the count or bounding-polygon positions diverge significantly,
    and UNSUPPORTED for non-image content.

    original_session fields used (read-only):
        qr_codes  : list[dict]  – each entry may have "points" (polygon) and
                                   "data" (decoded content, kept internal).
        ocr_boxes : list[dict]  – fallback if qr_codes absent.
    """
    if cleaned_content_type == "text":
        return CheckResult(name="QR_REDECODE", status="PASSED",
                           reason="Not applicable to plain text",
                           method_note="content-type routing")
    if cleaned_content_type != "image":
        return CheckResult(
            name="QR_REDECODE",
            status="UNSUPPORTED",
            reason="QR re-decode only applies to image content",
            method_note="cv2.QRCodeDetector (image only)",
        )

    try:
        import cv2  # noqa: PLC0415
        import numpy as np  # noqa: PLC0415

        img_array = np.frombuffer(cleaned_bytes, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if img is None:
            return CheckResult(
                name="QR_REDECODE",
                status="FAILED",
                reason="cv2 could not decode image bytes",
                method_note="cv2.imdecode",
            )

        detector = cv2.QRCodeDetector()
        # detectAndDecodeMulti returns (retval, decoded_info, points, straight_qrcode)
        retval, decoded_info, points, _ = detector.detectAndDecodeMulti(img)

        cleaned_qr_count = len(decoded_info) if (retval and decoded_info) else 0
        cleaned_points = points if (retval and points is not None) else []

        # An absent/invalid original QR inventory cannot establish that the
        # cleaned output retained or removed the expected codes.
        if not isinstance(original_session, dict) or not isinstance(original_session.get("qr_codes"), list):
            return CheckResult(name="QR_REDECODE", status="UNSUPPORTED",
                               reason="Original QR inventory unavailable",
                               method_note="cv2.QRCodeDetector; comparison unavailable")
        original_qr_codes = original_session["qr_codes"]
        original_qr_count = len(original_qr_codes)

        if original_qr_count == 0 and cleaned_qr_count == 0:
            # No QR codes expected and none found: trivial pass.
            return CheckResult(
                name="QR_REDECODE",
                status="PASSED",
                reason="No QR codes in original or cleaned image",
                method_note="cv2.QRCodeDetector (UNVERIFIED: no QR present)",
            )

        if cleaned_qr_count != original_qr_count:
            return CheckResult(
                name="QR_REDECODE",
                status="FAILED",
                reason=(
                    f"QR code count mismatch: original={original_qr_count}, "
                    f"cleaned={cleaned_qr_count}"
                ),
                method_note="cv2.QRCodeDetector",
            )

        # Compare polygons when an original location is available. Payloads
        # are deliberately ignored; cryptographic identity remains deferred.
        if original_qr_count:
            try:
                import numpy as np
                current = np.asarray(cleaned_points, dtype=float).reshape((-1, 4, 2))
                expected = []
                for entry in original_qr_codes:
                    pts = entry.get("points") if isinstance(entry, dict) else None
                    if pts is None:
                        return CheckResult(name="QR_REDECODE", status="UNSUPPORTED",
                                           reason="Original QR rectangles unavailable",
                                           method_note="rectangle comparison unavailable")
                    expected.append(np.asarray(pts, dtype=float).reshape((4, 2)))
                for lhs in expected:
                    if not any(np.allclose(lhs, rhs, atol=3.0) for rhs in current):
                        return CheckResult(name="QR_REDECODE", status="FAILED",
                                           reason="QR rectangle mismatch",
                                           method_note="cv2.QRCodeDetector rectangle comparison")
            except (TypeError, ValueError):
                return CheckResult(name="QR_REDECODE", status="UNSUPPORTED",
                                   reason="Original QR rectangles malformed",
                                   method_note="rectangle comparison unavailable")

        # NOTE: Signature/content verification is intentionally deferred.
        return CheckResult(
            name="QR_REDECODE",
            status="PASSED",
            reason=(
                f"QR code count matches ({cleaned_qr_count}). "
                "Content/signature verification UNVERIFIED (deferred)."
            ),
            method_note="cv2.QRCodeDetector (count match; signature NOT verified)",
        )

    except ImportError:
        return CheckResult(
            name="QR_REDECODE",
            status="UNSUPPORTED",
            reason="cv2 (opencv-python) not importable",
            method_note="cv2.QRCodeDetector (import failed)",
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            name="QR_REDECODE",
            status="FAILED",
            reason=f"Unexpected error during QR re-decode: {type(exc).__name__}",
            method_note="cv2.QRCodeDetector (error)",
        )


# ---------------------------------------------------------------------------
# Verdict helper
# ---------------------------------------------------------------------------


def _compute_verdict(checks: list[CheckResult]) -> str:
    """Derive overall verdict from individual check results.

    FAIL    if any check is FAILED.
    PARTIAL if all supported checks passed but at least one is UNSUPPORTED.
    CLEAN   if all checks are PASSED (none unsupported).
    """
    statuses = {c.status for c in checks}
    if "FAILED" in statuses:
        return "FAIL"
    if "UNSUPPORTED" in statuses:
        return "PARTIAL"
    return "CLEAN"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def verify_cleaned_output(
    *,
    original_session: Any,
    cleaned_bytes: bytes,
    cleaned_content_type: str,
    findings: list[dict[str, Any]],
) -> AuditResult:
    """Verify that ``cleaned_bytes`` contains no residual PII.

    Parameters
    ----------
    original_session:
        The session dict produced during the analyse step.  Read-only.
        Used by QR_REDECODE to compare bounding polygons.  May be ``None``
        or an empty dict if the session is unavailable.
    cleaned_bytes:
        In-memory bytes of the redacted document.  Never written to disk.
    cleaned_content_type:
        ``"text"`` or ``"image"``.
    findings:
        List of detected PII items from the original analysis.  Each entry
        should be a dict with at minimum ``"id"`` and either ``"type"`` or
        ``"sensitivity"``.  ``raw_value`` / ``value_masked`` are read
        transiently for STRING_SEARCH matching but NEVER stored in the result.

    Returns
    -------
    AuditResult
        Verdict is CLEAN, PARTIAL, or FAIL.
        ``ran`` counts checks that produced PASSED or FAILED (not UNSUPPORTED).
        Residuals contain only safe metadata — never raw values.

    Missing interfaces that cause UNSUPPORTED
    -----------------------------------------
    pipeline.detect_pii_pipeline  →  DETECTOR_RESCAN UNSUPPORTED
    (cv2 is available so QR_REDECODE is implemented and runs)
    """
    if not isinstance(cleaned_bytes, bytes) or not isinstance(findings, list):
        return AuditResult(verdict="PARTIAL", checks=[CheckResult(
            name="INPUT_VALIDATION", status="UNSUPPORTED",
            reason="Malformed audit inputs", method_note="input validation")], ran=0)
    if cleaned_content_type not in {"text", "image"}:
        from .audit import CheckResult as CR  # noqa: PLC0415
        return AuditResult(
            verdict="FAIL",
            checks=[
                CR(
                    name="INPUT_VALIDATION",
                    status="FAILED",
                    reason=f"Unknown cleaned_content_type: {cleaned_content_type!r}",
                )
            ],
            notes=["Audit aborted: invalid content type"],
            ran=0,
        )

    missing_interfaces: list[str] = []
    all_checks: list[CheckResult] = []
    all_residuals: list[ResidualHit] = []

    # 1. Detector re-scan (UNSUPPORTED – pipeline stub)
    all_checks.append(_check_detector_rescan(cleaned_bytes, cleaned_content_type, missing_interfaces))

    # 2. String search (implemented: stdlib re)
    string_check, string_residuals = _check_string_search(
        cleaned_bytes, cleaned_content_type, findings
    )
    all_checks.append(string_check)
    all_residuals.extend(string_residuals)

    # 3. Metadata inspection (implemented: Pillow + struct + zipfile)
    all_checks.append(_check_metadata_inspect(cleaned_bytes, cleaned_content_type))

    # 4. QR re-decode (implemented: cv2.QRCodeDetector)
    all_checks.append(
        _check_qr_redecode(cleaned_bytes, cleaned_content_type, original_session)
    )

    verdict = _compute_verdict(all_checks)

    # ran = checks that actually ran (PASSED or FAILED, not UNSUPPORTED)
    ran = sum(1 for c in all_checks if c.status in ("PASSED", "FAILED"))

    notes: list[str] = []
    if missing_interfaces:
        notes.append(
            "The following interfaces are not yet implemented and their checks "
            "are marked UNSUPPORTED: "
            + ", ".join(sorted(set(missing_interfaces)))
        )
    if verdict == "PARTIAL":
        notes.append(
            "Verdict is PARTIAL because one or more checks could not run. "
            "Do not treat PARTIAL as CLEAN."
        )

    return AuditResult(
        verdict=verdict,
        checks=all_checks,
        residuals=all_residuals,
        notes=notes,
        missing_interfaces=sorted(set(missing_interfaces)),
        ran=ran,
    )
