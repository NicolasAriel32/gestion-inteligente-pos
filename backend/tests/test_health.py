def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_host_restricted(client):
    assert client.get("/api/health", headers={"host": "evil.example"}).status_code == 400
