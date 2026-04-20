def test_health_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_root_returns_message(client):
    response = client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "environment" in data