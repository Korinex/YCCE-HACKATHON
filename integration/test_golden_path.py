"""Synthetic Contract v2 API golden path."""

from fastapi.testclient import TestClient

from server.app.main import app


def test_synthetic_text_analyze_redact_export_path():
    """Exercise analyze and redact using only server-side findings."""
    client = TestClient(app)
    analyzed = client.post("/api/v1/analyze", data={
        "content_type": "text",
        "text": "Synthetic test record: contact 555-0100",
    })
    assert analyzed.status_code == 200, (
        "BLOCKED: Backend 1 analyze/session API is still unimplemented"
    )
    payload = analyzed.json()
    decisions = [
        {
            "id": finding["id"],
            "action": "MASK",
            "decided_by_user": True,
        }
        for finding in payload["detected_items"]
    ]
    redacted = client.post("/api/v1/redact", json={
        "request_id": payload["request_id"],
        "decisions": decisions,
        "strict_mode": True,
    })
    assert redacted.status_code == 200, (
        "BLOCKED: Backend 1 redaction/export and session path is still unimplemented"
    )
