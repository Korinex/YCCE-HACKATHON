from fastapi.testclient import TestClient

try:
    from app.main import app
    from app.schemas import AnalyzeSummary, InternalFinding, PublicFinding
except ModuleNotFoundError:
    from server.app.main import app
    from server.app.schemas import AnalyzeSummary, InternalFinding, PublicFinding

client = TestClient(app)


def test_contract_models_serialize_expected_enums():
    internal = InternalFinding(
        id="pii_01",
        type="PAN",
        raw_value="ABCDE1234F",
        value_masked="ABCXXXX34F",
        is_valid=True,
        validation_method="PENDING",
        validation_reason="Pending implementation",
        confidence=0.0,
    )
    public_data = {
        key: value
        for key, value in internal.model_dump(exclude={"raw_value"}).items()
        if key in PublicFinding.model_fields
    }
    public_data["confidence_band"] = "LOW"
    item = PublicFinding.model_validate(public_data)
    serialized = item.model_dump()
    summary = AnalyzeSummary(
        total_pii_found=1,
        validated_pii_count=0,
        risk_score="LOW",
        breakdown={"PAN": 1},
    )
    assert internal.action == "MASK"
    assert "raw_value" not in serialized
    assert "original_filename" not in serialized
    assert summary.model_dump()["risk_score"] == "LOW"


def test_health_contract():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert set(response.json()) == {
        "status",
        "ocr_available",
        "pdf_available",
        "qr_available",
        "mode",
    }


def test_analyze_rejects_empty_text_before_feature_implementation():
    response = client.post(
        "/api/v1/analyze",
        data={"content_type": "text", "text": " "},
    )
    assert response.status_code == 422


def test_analyze_returns_safe_response_after_input_validation():
    response = client.post(
        "/api/v1/analyze",
        data={"content_type": "text", "text": "synthetic input"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "raw_value" not in body
    assert "original_filename" not in body
