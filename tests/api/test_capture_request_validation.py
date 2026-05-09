"""Request-body validation for /capture without database setup."""


def test_whitespace_only_raw_returns_422_and_skips_openai(client, monkeypatch):
    called: list[str] = []

    def must_not_parse(raw_text: str, client=None):
        called.append(raw_text)
        raise AssertionError("parse_capture_with_openai should not be called")

    monkeypatch.setattr(
        "app.services.capture_service.parse_capture_with_openai",
        must_not_parse,
    )
    response = client.post("/capture", json={"raw": "   "})
    assert response.status_code == 422
    assert called == []
