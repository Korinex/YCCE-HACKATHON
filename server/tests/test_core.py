from __future__ import annotations

import base64
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.redact_engine import render_text_redaction
from app.schemas import BoundingBox, InternalFinding, PublicFinding, SessionRecord, SESSION_TTL_SECONDS
from app.session import SessionStore


client = TestClient(app)


def test_schema_rejects_forbidden_public_fields():
    with pytest.raises(ValueError):
        PublicFinding(
            id="f1",
            type="PAN",
            raw_value="ABCDE1234F",
            value_masked="XXXXX1234F",
            is_valid=True,
            validation_method="test",
            validation_reason="test",
            confidence=0.9,
            confidence_band="HIGH",
            context_hit="pan",
        )


def test_schema_normalizes_bbox_and_context_hit_whitelist():
    bbox = BoundingBox(x=0.1, y=0.2, w=0.3, h=0.4)
    finding = PublicFinding(
        id="f2",
        type="AADHAAR",
        value_masked="XXXX",
        is_valid=False,
        validation_method="regex",
        validation_reason="candidate",
        confidence=0.7,
        confidence_band="MEDIUM",
        bbox={"x": bbox.x, "y": bbox.y, "w": bbox.w, "h": bbox.h},
        context_hit="aadhaar",
    )
    assert finding.bbox == {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4}
    assert finding.context_hit == "aadhaar"


def test_session_store_expiry_and_cleanup():
    store = SessionStore()
    store.clear_all()
    session = store.create(content_type="text", content="hello", ttl_seconds=1)
    assert store.get(session.request_id) is not None
    time.sleep(1.2)
    assert store.get(session.request_id) is None
    store.clear_all()


def test_session_api_creates_and_rejects_unknown_request_id():
    response = client.post("/api/v1/session", json={"content_type": "text", "ttl_seconds": 120})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["request_id"]

    unknown = client.get("/api/v1/session/does-not-exist")
    assert unknown.status_code == 404


def test_text_redaction_masks_and_removes_and_replace_token():
    text = "Aadhaar: 123456789012"
    items = [
        {"id": "f1", "char_span": [9, 21], "action": "MASK"},
        {"id": "f2", "char_span": [0, 8], "action": "REMOVE"},
    ]
    result = render_text_redaction(text, items, [])
    assert "Aadhaar" not in result
    assert "REDACTED" in result or "X" in result


def test_health_contract_unchanged():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "ocr_available": False}


def test_root_reports_skeleton_status():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "skeleton"


def test_analyze_rejects_empty_text():
    response = client.post("/api/v1/analyze", data={"content_type": "text", "text": " "})
    assert response.status_code == 422


def test_analyze_is_deferred_for_standard_synthetic_input():
    response = client.post("/api/v1/analyze", data={"content_type": "text", "text": "synthetic input"})
    assert response.status_code == 501
