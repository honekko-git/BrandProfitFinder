"""Tests for live connector HTTP client and error handling."""

from __future__ import annotations

import json

import httpx
import pytest

from marketplace.connectors.live.exceptions import MarketConnectorTransportError
from marketplace.connectors.live.http_client import MarketHttpClient


class _FakeResponse:
    def __init__(self, *, status_code: int = 200, payload: object | None = None) -> None:
        self.status_code = status_code
        self._payload = payload if payload is not None else {"ok": True}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://example.invalid/live")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("error", request=request, response=response)

    def json(self) -> object:
        return self._payload


class _FakeClient:
    def __init__(self, *, responses: list[_FakeResponse]) -> None:
        self._responses = list(responses)
        self.calls = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def get(self, url: str, params: dict[str, str] | None = None) -> _FakeResponse:
        self.calls += 1
        if not self._responses:
            raise httpx.ConnectError("connection failed", request=httpx.Request("GET", url))
        return self._responses.pop(0)


def test_market_http_client_returns_json_payload(monkeypatch) -> None:
    fake_client = _FakeClient(responses=[_FakeResponse(payload={"items": []})])
    monkeypatch.setattr("marketplace.connectors.live.http_client.httpx.Client", lambda **kwargs: fake_client)

    payload = MarketHttpClient(retry_count=0).get_json("https://example.invalid/live")

    assert payload == {"items": []}
    assert fake_client.calls == 1


def test_market_http_client_retries_on_transport_error(monkeypatch) -> None:
    fake_client = _FakeClient(
        responses=[
            _FakeResponse(status_code=503),
            _FakeResponse(payload={"items": [{"listing_id": "1"}]}),
        ]
    )
    monkeypatch.setattr("marketplace.connectors.live.http_client.httpx.Client", lambda **kwargs: fake_client)

    payload = MarketHttpClient(retry_count=1).get_json("https://example.invalid/live")

    assert payload["items"][0]["listing_id"] == "1"
    assert fake_client.calls == 2


def test_market_http_client_raises_transport_error_after_retries(monkeypatch) -> None:
    fake_client = _FakeClient(responses=[_FakeResponse(status_code=500), _FakeResponse(status_code=500)])
    monkeypatch.setattr("marketplace.connectors.live.http_client.httpx.Client", lambda **kwargs: fake_client)

    with pytest.raises(MarketConnectorTransportError):
        MarketHttpClient(retry_count=1).get_json("https://example.invalid/live")

    assert fake_client.calls == 2


def test_market_http_client_rejects_non_object_json(monkeypatch) -> None:
    fake_client = _FakeClient(responses=[_FakeResponse(payload=["not-an-object"])])
    monkeypatch.setattr("marketplace.connectors.live.http_client.httpx.Client", lambda **kwargs: fake_client)

    with pytest.raises(MarketConnectorTransportError):
        MarketHttpClient(retry_count=0).get_json("https://example.invalid/live")
