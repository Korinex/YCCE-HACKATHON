from fastapi.testclient import TestClient

from app.main import app
from app.schemas import AnalyzeSummary, DetectedItem

client = TestClient(app)


def test_contract_models_serialize_expected_enums():
    item = DetectedItem(
        id="pii_01",
        type="PAN",
        raw_value="ABCDE1234F",
        value_masked="ABCXXXX34F",
        is_valid=True,
        validation_method="PENDING",
        validation_reason="Pending implementation",
        confidence=0.0,
    )
    summary = AnalyzeSummary(
        total_pii_found=1,
        validated_pii_count=0,
        risk_score="LOW",
        breakdown={"PAN": 1},
    )
    assert item.action == "MASK"
    assert summary.model_dump()["risk_score"] == "LOW"


def test_health_contract():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "ocr_available": False}


def test_analyze_rejects_empty_text_before_feature_implementation():
    response = client.post(
        "/api/v1/analyze",
        data={"content_type": "text", "text": " "},
    )
    assert response.status_code == 422


def test_analyze_is_explicitly_deferred_after_input_validation():
    response = client.post(
        "/api/v1/analyze",
        data={"content_type": "text", "text": "synthetic input"},
    )
    assert response.status_code == 501
