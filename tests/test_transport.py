"""Unit tests for Version 2 marketplace HTTP transport."""

from __future__ import annotations

import logging
from typing import Any

import httpx
import pytest

from config.transport import TransportSettings
from utils.transport import (
    HttpTransport,
    MarketplaceAuthenticationError,
    MarketplaceConnectionError,
    MarketplaceRateLimitError,
    MarketplaceTimeoutError,
    MarketplaceTransportError,
)
from utils.transport.logging_utils import redact_headers, redact_url
from utils.transport.retry import compute_backoff_seconds


def _settings(max_retries: int = 2, **overrides: Any) -> TransportSettings:
    base = {
        "timeout_seconds": 5.0,
        "max_retries": max_retries,
        "backoff_base_seconds": 0.0,
        "backoff_max_seconds": 0.0,
    }
    base.update(overrides)
    return TransportSettings(**base)


def _transport(handler, *, max_retries: int = 2) -> HttpTransport:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return HttpTransport(
        marketplace_name="demo_market",
        settings=_settings(max_retries=max_retries),
        client=client,
    )


def test_successful_get_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.params["q"] == "sku-1"
        return httpx.Response(200, json={"ok": True})

    transport = _transport(handler)
    response = transport.get("https://api.example.com/search", params={"q": "sku-1"})

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert response.retry_count == 0
    assert response.metadata["marketplace_name"] == "demo_market"


def test_successful_post_request() -> None:
    import json

    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["json"] = json.loads(request.content)
        return httpx.Response(201, json={"created": True})

    transport = _transport(handler)
    response = transport.post("https://api.example.com/items", json={"sku": "abc"})

    assert seen["method"] == "POST"
    assert response.status_code == 201
    assert response.json() == {"created": True}


def test_timeout_retries_then_raises() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        raise httpx.TimeoutException("timeout")

    transport = _transport(handler, max_retries=2)
    with pytest.raises(MarketplaceTimeoutError) as exc_info:
        transport.get("https://api.example.com/items")

    assert attempts["count"] == 3
    assert exc_info.value.marketplace_name == "demo_market"
    assert exc_info.value.retry_count == 2


def test_connection_error_retries_then_raises() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        raise httpx.ConnectError("connection refused")

    transport = _transport(handler, max_retries=1)
    with pytest.raises(MarketplaceConnectionError):
        transport.get("https://api.example.com/items")

    assert attempts["count"] == 2


def test_retry_success_after_transient_500() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(500, json={"error": "server"})
        return httpx.Response(200, json={"ok": True})

    transport = _transport(handler, max_retries=2)
    response = transport.get("https://api.example.com/items")

    assert response.status_code == 200
    assert response.retry_count == 1
    assert attempts["count"] == 2


def test_retry_exhaustion_on_500() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(503, json={"error": "unavailable"})

    transport = _transport(handler, max_retries=2)
    with pytest.raises(MarketplaceTransportError) as exc_info:
        transport.get("https://api.example.com/items")

    assert attempts["count"] == 3
    assert exc_info.value.status_code == 503
    assert exc_info.value.retry_count == 2


def test_429_retries_then_raises_rate_limit_error() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(429, json={"error": "rate limit"})

    transport = _transport(handler, max_retries=2)
    with pytest.raises(MarketplaceRateLimitError) as exc_info:
        transport.get("https://api.example.com/items")

    assert attempts["count"] == 3
    assert exc_info.value.status_code == 429


def test_authentication_failure_is_not_retried() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(401, json={"error": "unauthorized"})

    transport = _transport(handler, max_retries=3)
    with pytest.raises(MarketplaceAuthenticationError) as exc_info:
        transport.get("https://api.example.com/items")

    assert attempts["count"] == 1
    assert exc_info.value.status_code == 401


def test_403_raises_authentication_error_without_retry() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(403, json={"error": "forbidden"})

    transport = _transport(handler, max_retries=3)
    with pytest.raises(MarketplaceAuthenticationError):
        transport.get("https://api.example.com/items")

    assert attempts["count"] == 1


def test_404_is_not_retried() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(404, json={"error": "missing"})

    transport = _transport(handler, max_retries=3)
    with pytest.raises(MarketplaceTransportError):
        transport.get("https://api.example.com/items")

    assert attempts["count"] == 1


def test_backoff_sequence() -> None:
    settings = TransportSettings(
        timeout_seconds=5.0,
        max_retries=3,
        backoff_base_seconds=1.0,
        backoff_max_seconds=4.0,
    )
    assert compute_backoff_seconds(0, settings) == 1.0
    assert compute_backoff_seconds(1, settings) == 2.0
    assert compute_backoff_seconds(2, settings) == 4.0
    assert compute_backoff_seconds(3, settings) == 4.0


def test_logging_redacts_secrets(caplog) -> None:
    caplog.set_level(logging.INFO, logger="utils.transport.logging_utils")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    transport = HttpTransport(
        marketplace_name="secure_market",
        settings=_settings(max_retries=0),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        default_headers={
            "Authorization": "Bearer secret-token",
            "X-API-Key": "abc123",
        },
    )

    transport.get("https://api.example.com/search?api_key=supersecret&page=1")

    transport_records = [
        record for record in caplog.records if record.name == "utils.transport.logging_utils"
    ]
    assert transport_records
    combined = "\n".join(record.getMessage() for record in transport_records)
    for record in transport_records:
        payload = getattr(record, "transport", {})
        combined += str(payload)
    assert "secret-token" not in combined
    assert "abc123" not in combined
    assert "supersecret" not in combined
    assert "secure_market" in combined
    assert any(getattr(record, "transport", {}).get("response_status") == 200 for record in transport_records)


def test_redact_helpers() -> None:
    assert redact_headers({"Authorization": "Bearer abc"})["Authorization"] == "***REDACTED***"
    assert "supersecret" not in redact_url("https://api.example.com?api_key=supersecret&q=1")


def test_structured_log_payload_includes_retry_and_elapsed(caplog) -> None:
    caplog.set_level(logging.INFO, logger="utils.transport.logging_utils")
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(502, json={"error": "bad gateway"})
        return httpx.Response(200, json={"ok": True})

    transport = _transport(handler, max_retries=1)
    transport.get("https://api.example.com/items")

    records = [record for record in caplog.records if getattr(record, "transport", None)]
    assert records
    payload = records[-1].transport
    assert payload["marketplace_name"] == "demo_market"
    assert payload["retry_count"] >= 0
    assert payload["elapsed_ms"] is not None
