from fastapi.testclient import TestClient

from app.main import app


def test_health(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    with TestClient(app, base_url="http://localhost") as client:
        assert client.get("/api/health").json() == {"status": "ok"}

def test_host_restricted(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    with TestClient(app, base_url="http://localhost") as client:
        assert client.get("/api/health", headers={"host": "evil.example"}).status_code == 400
