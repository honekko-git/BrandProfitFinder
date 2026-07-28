"""Foundation tests for utils.http (no real network)."""

from unittest.mock import MagicMock

import httpx
import pytest

from utils.http import HttpClient, build_headers, fetch_url


def test_build_headers_contains_user_agent() -> None:
    headers = build_headers()
    assert "User-Agent" in headers
    assert headers["Accept"]


def test_http_client_fetch_text_with_injected_client() -> None:
    mock_response = MagicMock()
    mock_response.text = "<html>ok</html>"
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.get.return_value = mock_response

    client = HttpClient(client=mock_client)
    result = client.fetch_text("https://example.com")

    assert result == "<html>ok</html>"
    mock_client.get.assert_called_once_with("https://example.com")


def test_fetch_url_raises_on_http_error() -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "error",
        request=httpx.Request("GET", "https://example.com"),
        response=httpx.Response(500),
    )

    mock_client = MagicMock()
    mock_client.get.return_value = mock_response

    client = HttpClient(client=mock_client)
    with pytest.raises(httpx.HTTPStatusError):
        client.fetch_text("https://example.com")


def test_module_level_fetch_url_uses_client(monkeypatch) -> None:
    called: dict[str, str] = {}

    class _FakeClient:
        def __init__(self, timeout: int | None = None) -> None:
            self.timeout = timeout

        def fetch_text(self, url: str) -> str:
            called["url"] = url
            return "mocked"

    monkeypatch.setattr("utils.http.HttpClient", _FakeClient)
    assert fetch_url("https://example.com") == "mocked"
    assert called["url"] == "https://example.com"
