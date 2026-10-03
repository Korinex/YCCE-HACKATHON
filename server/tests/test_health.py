from fastapi.testclient import TestClient

try:
    from app.main import app
except ModuleNotFoundError:
    from server.app.main import app


def test_root_reports_skeleton_status():
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
