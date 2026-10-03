"""SCOUT text/OCR finding pipeline. Findings are candidates, not identity claims."""

from __future__ import annotations

import re
from typing import Any

from app.validators.aadhaar import validate_aadhaar, validate_vid
from app.validators.financial import validate_financial_value
from app.validators.pan import validate_pan

_TRANSLATION = str.maketrans(
    "०१२३४५६७८९٠١٢٣٤٥٦٧٨٩", "01234567890123456789"
)
_CONTEXT = {
    "AADHAAR": r"aadhaar|aadhar|uidai",
    "VID": r"\bvid\b|virtual id",
    "PAN": r"\bpan\b|permanent account",
    "GSTIN": r"gstin|gst number|goods and services tax",
    "IFSC": r"ifsc",
    "BANK_ACCOUNT": r"account|a/c|bank|ifsc",
    "UPI": r"upi|payment address|vpa",
    "PASSPORT": r"passport|travel document",
    "VOTER_ID": r"voter|epic|election card",
    "DRIVING_LICENCE": r"driving licence|driving license|\bdl no\b",
    "VEHICLE": r"vehicle|registration no|\breg no\b|number plate",
}
_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("AADHAAR", re.compile(r"(?<!\d)[2-9]\d{11}(?!\d)")),
    ("VID", re.compile(r"(?<!\d)1\d{15}(?!\d)")),
    ("CREDIT_CARD", re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")),
    ("GSTIN", re.compile(r"(?<![A-Z0-9])\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9](?![A-Z0-9])", re.I)),
    ("PAN", re.compile(r"(?<![A-Z0-9])[A-Z]{3}[ABCFGHLJPT][A-Z]\d{4}[A-Z](?![A-Z0-9])", re.I)),
    ("IFSC", re.compile(r"(?<![A-Z0-9])[A-Z]{4}0[A-Z0-9]{6}(?![A-Z0-9])", re.I)),
    ("PASSPORT", re.compile(r"(?<![A-Z0-9])[A-Z][ -]?\d{7}(?!\d)", re.I)),
    ("VOTER_ID", re.compile(r"(?<![A-Z0-9])[A-Z]{3}[ -]?\d{7}(?!\d)", re.I)),
    ("DRIVING_LICENCE", re.compile(r"(?<![A-Z0-9])\d{2}[ -]?(?:19|20)?\d{2}[ -]?[A-Z]{1,3}[ -]?\d{4,11}(?![A-Z0-9])", re.I)),
    ("VEHICLE", re.compile(r"(?<![A-Z0-9])(?:[A-Z]{2}[ -]?\d{1,2}[ -]?(?:[A-Z]{1,3}[ -]?)?\d{4})(?![A-Z0-9])", re.I)),
    ("UPI", re.compile(r"(?<![\w.+-])[A-Z0-9._-]{2,256}@[A-Z][A-Z0-9.-]{1,63}(?![\w.-])", re.I)),
    ("EMAIL", re.compile(r"(?<![\w.+-])[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?(?:\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)+(?![\w.-])", re.I)),
    ("PHONE", re.compile(r"(?<!\d)(?:(?:\+?91)[ -]?)?[6-9](?:[ -]?\d){9}(?!\d)")),
    ("BANK_ACCOUNT", re.compile(r"(?<!\d)\d{9,18}(?!\d)")),
]
_HEALTH = re.compile(
    r"\b(?:diagnosis|diabetes|hiv|pregnan(?:t|cy)|mental health|depression|"
    r"anxiety disorder|prescription|test result|medical report|cancer|"
    r"blood pressure|medication|病|रक्तचाप)\b", re.I,
)
_KNOWN_STRENGTH = {"VALIDATED": 1.0, "FORMAT_ONLY": 0.6, "REVIEW": 0.35}
_RULE_NAMES = {
    "AADHAAR": "aadhaar.verhoeff.v1", "VID": "vid.format.v1", "PAN": "pan.format.v1",
    "GSTIN": "gstin.format.v1", "IFSC": "ifsc.format.v1", "BANK_ACCOUNT": "bank_account.context.v1",
    "UPI": "upi.suffix.v1", "PHONE": "phone.india.v1", "CREDIT_CARD": "card.luhn.v1",
    "PASSPORT": "passport.context.v1", "VOTER_ID": "voter_id.context.v1",
    "DRIVING_LICENCE": "driving_licence.context.v1", "VEHICLE": "vehicle.context.v1",
    "EMAIL": "email.format.v1", "HEALTH_TERM": "health.lexicon.v1",
}


def _sensitivity(kind: str) -> str:
    if kind in {"AADHAAR", "VID", "PAN", "PASSPORT", "VOTER_ID", "DRIVING_LICENCE"}:
        return "GOVT_ID"
    if kind in {"BANK_ACCOUNT", "IFSC", "UPI", "CREDIT_CARD", "GSTIN"}:
        return "FINANCIAL"
    if kind in {"PHONE", "EMAIL"}:
        return "CONTACT"
    if kind == "HEALTH_TERM":
        return "HEALTH"
    if kind == "VEHICLE":
        return "VEHICLE_ID"
    return "OTHER"


def _context_hits(text: str, start: int, end: int, kind: str) -> list[str]:
    pattern = _CONTEXT.get(kind)
    if not pattern:
        return []
    window = text[max(0, start - 40):min(len(text), end + 40)]
    return list(dict.fromkeys(match.group(0).lower() for match in re.finditer(pattern, window, re.I)))[:3]


def normalize_digits(text: str) -> str:
    """Convert Devanagari and Arabic-Indic digits while preserving string offsets."""
    return text.translate(_TRANSLATION)


def _in_context(text: str, start: int, end: int, kind: str) -> bool:
    pattern = _CONTEXT.get(kind)
    if not pattern:
        return False
    return bool(re.search(pattern, text[max(0, start - 40):min(len(text), end + 40)], re.I))


def _classify(kind: str, raw: str, text: str, start: int, end: int) -> tuple[str, str]:
    contextual = _in_context(text, start, end, kind)
    if kind == "AADHAAR":
        valid, reason = validate_aadhaar(raw)
        return ("VALIDATED", reason) if valid else ("REVIEW", reason)
    if kind == "VID":
        valid, reason = validate_vid(raw)
        return ("FORMAT_ONLY", reason) if valid and contextual else ("REVIEW", "CONTEXT_REQUIRED" if valid else reason)
    if kind == "PAN":
        valid, reason = validate_pan(raw)
        return ("FORMAT_ONLY", reason) if valid else ("REVIEW", reason)
    if kind in {"IFSC", "GSTIN", "PHONE", "CREDIT_CARD", "UPI"}:
        valid, reason = validate_financial_value(kind, raw)
        if kind == "UPI":
            if "KNOWN_SUFFIX" in reason:
                return "VALIDATED", reason
            return "REVIEW", reason
        return ("FORMAT_ONLY", reason) if valid else ("REVIEW", reason)
    if kind == "BANK_ACCOUNT":
        valid, reason = validate_financial_value(kind, raw)
        return ("FORMAT_ONLY", reason) if valid and contextual else ("REVIEW", "CONTEXT_REQUIRED" if valid else reason)
    if kind == "EMAIL":
        return "FORMAT_ONLY", "FORMAT_MATCH; FORMAT_ONLY"
    if kind in {"PASSPORT", "VOTER_ID", "DRIVING_LICENCE", "VEHICLE"}:
        return ("FORMAT_ONLY", "FORMAT_MATCH; ISSUER_NOT_CHECKED") if contextual else ("REVIEW", "CONTEXT_REQUIRED")
    return "REVIEW", "HUMAN_REVIEW_REQUIRED"


def _masked(kind: str, raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if kind == "EMAIL" and "@" in raw:
        local, domain = raw.rsplit("@", 1)
        return (local[:1] + "***@" + domain) if local else "***@" + domain
    if len(digits) >= 4:
        return "X" * (len(raw) - 4) + raw[-4:]
    return "[REDACTED]"


def _finding(kind: str, text: str, start: int, end: int, ocr_confidence: float = 1.0,
             bounding_box: dict[str, int] | None = None, source: str = "text") -> dict[str, Any]:
    raw = text[start:end]
    tier, reason = _classify(kind, raw, text, start, end)
    score = _KNOWN_STRENGTH[tier] * min(1.0, max(0.0, ocr_confidence) / 0.9)
    confidence_band = "HIGH" if score >= 0.75 else "MEDIUM" if score >= 0.50 else "LOW"
    return {
        "id": f"f_{start}_{end}_{kind.lower()}", "type": kind, "raw_value": raw,
        "value_masked": _masked(kind, raw), "is_valid": tier == "VALIDATED",
        "validation_method": "SCOUT_DETERMINISTIC", "validation_reason": reason,
        "validation_tier": tier, "confidence": round(score, 4),
        "confidence_band": confidence_band, "start": start, "end": end,
        "bounding_box": bounding_box, "action": "MASK",
        "rule": _RULE_NAMES.get(kind, "scout.pattern.v1"),
        "context_hit": _context_hits(text, start, end, kind),
        "sensitivity": _sensitivity(kind),
        "source": source,
        "ocr_confidence": round(ocr_confidence, 4) if source == "ocr" else None,
        "page": None,
        "review_required": tier == "REVIEW" or confidence_band != "HIGH",
    }


def detect_text(text: str, ocr_tokens: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Return overlapping-resolved findings; source offsets refer to normalized text."""
    text = normalize_digits(text or "")
    candidates: list[dict[str, Any]] = []
    for kind, pattern in _RULES:
        for match in pattern.finditer(text):
            raw = match.group()
            # Don't interpret an ordinary email address as a UPI handle.
            if kind == "UPI" and "." in raw.rsplit("@", 1)[-1] and not _in_context(text, *match.span(), "UPI"):
                continue
            if kind == "PHONE" and len(re.sub(r"\D", "", raw)) not in {10, 12}:
                continue
            # Generic bank-like digit strings are findings only with nearby context.
            if kind == "BANK_ACCOUNT" and not _in_context(text, *match.span(), kind):
                continue
            candidates.append({"kind": kind, "start": match.start(), "end": match.end()})
    for match in _HEALTH.finditer(text):
        candidates.append({"kind": "HEALTH_TERM", "start": match.start(), "end": match.end()})

    # Longest span wins; for ties Aadhaar wins before phone/account patterns.
    rank = {kind: index for index, (kind, _) in enumerate(_RULES)}
    candidates.sort(key=lambda item: (-(item["end"] - item["start"]), rank.get(item["kind"], 999), item["start"]))
    accepted: list[dict[str, Any]] = []
    for item in candidates:
        if any(item["start"] < other["end"] and other["start"] < item["end"] for other in accepted):
            continue
        accepted.append(item)
    accepted.sort(key=lambda item: item["start"])

    output = []
    for item in accepted:
        conf = 1.0
        box = None
        if ocr_tokens:
            matched = [token for token in ocr_tokens if token.get("start", 0) < item["end"] and token.get("end", 0) > item["start"]]
            if matched:
                conf = min(float(token.get("confidence", 0.0)) for token in matched)
                boxes = [token.get("bounding_box") for token in matched if token.get("bounding_box")]
                if boxes:
                    left = min(b["x"] for b in boxes); top = min(b["y"] for b in boxes)
                    right = max(b["x"] + b["w"] for b in boxes); bottom = max(b["y"] + b["h"] for b in boxes)
                    box = {"x": left, "y": top, "w": right-left, "h": bottom-top}
        output.append(_finding(item["kind"], text, item["start"], item["end"], conf, box,
                               source="ocr" if ocr_tokens is not None else "text"))
    return output


def analyze_image(image_bytes: bytes) -> dict[str, Any]:
    from app.ocr_engine import extract_text_and_boxes

    tokens = extract_text_and_boxes(image_bytes)
    text_parts: list[str] = []
    cursor = 0
    for token in tokens:
        value = str(token.get("text", "")).strip()
        if not value:
            continue
        if text_parts:
            cursor += 1
        token["start"], token["end"] = cursor, cursor + len(value)
        text_parts.append(value)
        cursor += len(value)
    text = " ".join(text_parts)
    findings = detect_text(text, tokens) if text else []
    average_confidence = sum(t.get("confidence", 0) for t in tokens) / len(tokens) if tokens else 0.0
    quality = "UNREADABLE" if not text or average_confidence < 0.35 else "DEGRADED" if average_confidence < 0.7 else "GOOD"
    warnings = [] if quality == "GOOD" else [f"OCR_{quality}_REVIEW_REQUIRED"]
    return {"extracted_text": text, "detected_items": findings, "ocr_tokens": tokens,
            "page_quality": quality, "review_required": quality != "GOOD",
            "warnings": warnings}


def detect_pii_pipeline(text: str | None = None, image_bytes: bytes | None = None) -> list[dict]:
    """Compatibility interface: detect text or image findings without API wiring."""
    if text is not None:
        return detect_text(text)
    if image_bytes is not None:
        return analyze_image(image_bytes)["detected_items"]
    return []
