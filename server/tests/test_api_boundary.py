from app.api_boundary import apply_decisions_to_api_findings, findings_for_api
from app.pipeline import detect_text


def test_api_adapter_masks_raw_values_and_uses_frozen_finding_shape():
    internal = detect_text("PAN ABCPE1234F")[0]
    public = findings_for_api([internal])[0]

    assert internal["raw_value"] == "ABCPE1234F"
    assert public == {
        "id": internal["id"],
        "type": "PAN",
        "raw_masked": f"XXXXXX234F | {internal['id']}",
        "validity_class": "FORMAT_ONLY",
        "confidence": 0.6,
        "confidence_band": "MEDIUM",
        "rule": "pan.format.v1",
        "reason": "FORMAT_MATCH; FORMAT_ONLY; ISSUER_NOT_CHECKED; CONTEXT_MATCH",
        "context_hit": ["pan"],
        "sensitivity": "GOVT_ID",
        "source": "text",
        "ocr_confidence": None,
        "page": None,
        "bbox": None,
        "default_action": "MASK",
        "decided": False,
    }
    assert "raw_value" not in public
    assert internal["raw_value"] not in repr(public)


def test_api_adapter_adds_pixel_space_bbox_and_decisions_without_mutating():
    internal = detect_text("PAN ABCPE1234F", [
        {"start": 4, "end": 14, "confidence": 0.9,
         "bounding_box": {"x": 12, "y": 4, "w": 50, "h": 9}}
    ])[0]
    public = findings_for_api([internal])
    assert public[0]["source"] == "ocr"
    assert "OCR_REVIEW" in public[0]["reason"]
    assert public[0]["ocr_confidence"] == 0.9
    assert public[0]["bbox"] == {"x": 12, "y": 4, "w": 50, "h": 9, "space": "pixels"}

    decided = apply_decisions_to_api_findings(public, [
        {"id": internal["id"], "action": "MASK", "decided_by_user": True}
    ])
    assert decided[0]["decided"] is True
    assert public[0]["decided"] is False
