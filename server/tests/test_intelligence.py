from app.pipeline import analyze_image, detect_text, normalize_digits
from app.validators.aadhaar import validate_aadhaar, validate_vid
from app.validators.financial import luhn_valid, validate_financial_value
from app.validators.pan import validate_pan


def test_aadhaar_required_vectors_and_checksum_failure():
    for value in (
        "234123412346", "999941057058", "999988887779", "345678901238",
        "876543210988", "600011122234", "455566677786", "999999999999",
    ):
        assert validate_aadhaar(value)[0], value
    for value in ("999999999998", "123456789012", "987654321098", "234123412345"):
        assert not validate_aadhaar(value)[0], value


def test_pan_entity_and_format_only():
    valid, reason = validate_pan("ABCPE1234F")
    assert valid and "FORMAT_ONLY" in reason
    assert not validate_pan("ABCQE1234F")[0]


def test_indic_digit_normalization_preserves_digit_offsets():
    text = "Aadhaar: ९९९९४१०५७०५८"
    normalized = normalize_digits(text)
    assert normalized == "Aadhaar: 999941057058"
    finding = detect_text(text)[0]
    assert normalized[finding["start"]:finding["end"]] == finding["raw_value"] == "999941057058"


def test_bank_account_needs_context_and_longest_match_wins():
    assert not detect_text("Reference 123456789012")[0:1]
    items = detect_text("Aadhaar 234123412346 and account 123456789012")
    assert [item["type"] for item in items] == ["AADHAAR", "BANK_ACCOUNT"]
    assert items[0]["validation_tier"] == "VALIDATED"
    assert all(item["end"] > item["start"] for item in items)


def test_financial_validator_boundaries():
    assert validate_financial_value("IFSC", "HDFC0001234")[0]
    assert validate_financial_value("PHONE", "+91 9876543210")[0]
    assert validate_financial_value("UPI", "user@oksbi")[0]
    assert not validate_financial_value("UPI", "user@gmail.com")[0]
    assert luhn_valid("4111111111111111")
    assert validate_vid("1234567890123456")[0]


def test_context_limited_document_ids_and_health_are_review():
    values = detect_text("Passport A1234567, diabetes medication")
    assert [item["type"] for item in values] == ["PASSPORT", "HEALTH_TERM", "HEALTH_TERM"]
    assert values[0]["validation_tier"] == "FORMAT_ONLY"
    assert values[1]["validation_tier"] == "REVIEW"


def test_ocr_findings_retain_confidence_and_union_box():
    text = "PAN ABCPE1234F"
    tokens = [
        {"start": 0, "end": 3, "confidence": 0.9, "bounding_box": {"x": 2, "y": 4, "w": 8, "h": 9}},
        {"start": 4, "end": 14, "confidence": 0.72, "bounding_box": {"x": 12, "y": 4, "w": 50, "h": 9}},
    ]
    finding = detect_text(text, tokens)[0]
    assert finding["bounding_box"] == {"x": 12, "y": 4, "w": 50, "h": 9}
    assert finding["confidence"] < 0.6


def test_ocr_quality_fails_closed_when_empty_or_weak(monkeypatch):
    import app.ocr_engine

    monkeypatch.setattr(app.ocr_engine, "extract_text_and_boxes", lambda _: [])
    unreadable = analyze_image(b"image")
    assert unreadable["page_quality"] == "UNREADABLE"
    assert unreadable["review_required"]

    monkeypatch.setattr(app.ocr_engine, "extract_text_and_boxes", lambda _: [
        {"text": "example", "confidence": 0.5, "bounding_box": {"x": 1, "y": 1, "w": 10, "h": 5}}
    ])
    degraded = analyze_image(b"image")
    assert degraded["page_quality"] == "DEGRADED"
    assert degraded["review_required"]
