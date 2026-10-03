import json
from pathlib import Path


VECTORS = Path(__file__).parent / "vectors"


def test_public_finding_fixture_is_masked_and_covers_c1_cases():
    fixture = json.loads((VECTORS / "backend2_public_findings.json").read_text(encoding="utf-8"))
    findings = fixture["findings"]
    assert all("raw_value" not in finding for finding in findings)
    assert all(any(mask in finding["raw_masked"].split(" | ")[0] for mask in ("X", "[REDACTED]", "***")) for finding in findings)
    assert {finding["validity_class"] for finding in findings} >= {"VALIDATED", "FORMAT_ONLY", "REVIEW"}
    assert any(finding["source"] == "ocr" and finding["bbox"] and finding["ocr_confidence"] for finding in findings)
    failed = next(finding for finding in findings if "CHECKSUM_FAIL" in finding["reason"])
    assert failed["validity_class"] == "REVIEW"
    email = next(finding for finding in findings if finding["type"] == "EMAIL")
    assert fixture["negative_expectations"]["ordinary_email_is_upi"] is False
    assert not any(finding["type"] == "UPI" and finding["id"] == email["id"] for finding in findings)


def test_degradation_fixture_covers_c6_states_without_payloads():
    fixture = json.loads((VECTORS / "backend2_degradation.json").read_text(encoding="utf-8"))
    scenarios = {scenario["id"]: scenario for scenario in fixture["scenarios"]}
    assert set(scenarios) == {
        "ocr_unavailable", "ocr_empty_result", "ocr_low_confidence",
        "unsupported_script_or_handwriting", "qr_unsupported", "qr_present_unverified",
    }
    for scenario_id in ("qr_unsupported", "qr_present_unverified"):
        expected = scenarios[scenario_id]["expected"]
        assert expected["raw_payload_returned"] is False
        assert expected["must_not_claim_verified"] is True
