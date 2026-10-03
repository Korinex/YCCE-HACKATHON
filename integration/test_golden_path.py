"""Synthetic API golden path. This is expected to fail until Backend 1 wires APIs."""

from fastapi.testclient import TestClient

from server.app.main import app


def test_synthetic_text_analyze_redact_export_path():
    """Exercise the real API; a 501 response must fail this readiness test."""
    client = TestClient(app)
    analyzed = client.post("/api/v1/analyze", data={
        "content_type": "text",
        "text": "Synthetic test record: contact 555-0100",
    })
    assert analyzed.status_code == 200, (
        "BLOCKED: Backend 1 analyze/session API is still unimplemented"
    )
    payload = analyzed.json()
    redacted = client.post("/api/v1/redact", json={
        "request_id": payload["request_id"],
        "content_type": "text",
        "text": payload.get("extracted_text"),
        "detected_items": payload.get("detected_items", []),
        "redaction_rules": [],
    })
    assert redacted.status_code == 200, (
        "BLOCKED: Backend 1 redaction/export and session path is still unimplemented"
    )
