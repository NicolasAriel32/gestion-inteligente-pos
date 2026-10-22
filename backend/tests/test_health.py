from fastapi.testclient import TestClient
from app.main import app

def test_health():
    with TestClient(app, base_url="http://localhost") as client:
        assert client.get("/api/health").json() == {"status": "ok"}

def test_host_restricted():
    with TestClient(app, base_url="http://localhost") as client:
        assert client.get("/api/health", headers={"host": "evil.example"}).status_code == 400
