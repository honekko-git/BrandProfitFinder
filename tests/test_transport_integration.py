"""Integration tests for Fake Marketplace Adapter + HttpTransport."""

from __future__ import annotations

import logging
from typing import Any

import httpx
import pytest

from config.transport import TransportSettings
from tests.support.fake_marketplace_adapter import FakeMarketplaceAdapter
from utils.transport import (
    HttpTransport,
    MarketplaceAuthenticationError,
    MarketplaceRateLimitError,
    MarketplaceTransportError,
    TransportResponse,
)


def _settings(max_retries: int = 2, **overrides: Any) -> TransportSettings:
    base = {
        "timeout_seconds": 5.0,
        "max_retries": max_retries,
        "backoff_base_seconds": 0.0,
        "backoff_max_seconds": 0.0,
    }
    base.update(overrides)
    return TransportSettings(**base)


def _adapter(
    handler,
    *,
    marketplace_name: str = "fake_stockx",
    max_retries: int = 2,
    headers: dict[str, str] | None = None,
) -> FakeMarketplaceAdapter:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    transport = HttpTransport(
        marketplace_name=marketplace_name,
        settings=_settings(max_retries=max_retries),
        client=client,
        default_headers=headers or {},
    )
    return FakeMarketplaceAdapter(marketplace_name=marketplace_name, transport=transport)


def test_successful_request_flow_adapter_to_transport_response() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["query"] = request.url.params["q"]
        captured["marketplace_header"] = request.headers.get("X-Marketplace-Id", "")
        return httpx.Response(
            200,
            json={"listings": [{"listing_id": "L-1", "title": "Demo Sneaker"}]},
        )

    adapter = _adapter(
        handler,
        headers={"X-Marketplace-Id": "fake_stockx"},
    )
    response = adapter.fetch_listings("SKU-123")
    payload = adapter.search_listings("SKU-123")

    assert captured["method"] == "GET"
    assert captured["query"] == "SKU-123"
    assert captured["marketplace_header"] == "fake_stockx"
    assert isinstance(response, TransportResponse)
    assert response.status_code == 200
    assert response.retry_count == 0
    assert response.metadata["marketplace_name"] == "fake_stockx"
    assert response.metadata["operation"] == "search_listings"
    assert payload["listings"][0]["listing_id"] == "L-1"


def test_retry_success_first_500_then_200() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(500, json={"error": "temporary"})
        return httpx.Response(200, json={"listings": []})

    adapter = _adapter(handler, max_retries=2)
    response = adapter.fetch_listings("query")

    assert attempts["count"] == 2
    assert response.status_code == 200
    assert response.retry_count == 1


def test_retry_exhaustion_all_503_responses() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(503, json={"error": "unavailable"})

    adapter = _adapter(handler, max_retries=2)
    with pytest.raises(MarketplaceTransportError) as exc_info:
        adapter.search_listings("query")

    assert attempts["count"] == 3
    assert exc_info.value.status_code == 503
    assert exc_info.value.marketplace_name == "fake_stockx"
    assert exc_info.value.retry_count == 2


def test_rate_limit_429_raises_after_retries() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(429, json={"error": "rate limit"})

    adapter = _adapter(handler, max_retries=2)
    with pytest.raises(MarketplaceRateLimitError) as exc_info:
        adapter.fetch_listings("query")

    assert attempts["count"] == 3
    assert exc_info.value.status_code == 429
    assert exc_info.value.marketplace_name == "fake_stockx"


def test_authentication_failure_401_no_retry() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(401, json={"error": "unauthorized"})

    adapter = _adapter(handler, max_retries=3)
    with pytest.raises(MarketplaceAuthenticationError) as exc_info:
        adapter.search_listings("query")

    assert attempts["count"] == 1
    assert exc_info.value.status_code == 401


def test_authentication_failure_403_no_retry() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(403, json={"error": "forbidden"})

    adapter = _adapter(handler, max_retries=3)
    with pytest.raises(MarketplaceAuthenticationError):
        adapter.search_listings("query")

    assert attempts["count"] == 1


def test_logging_records_marketplace_retry_and_elapsed_without_secrets(caplog) -> None:
    caplog.set_level(logging.INFO, logger="utils.transport.logging_utils")
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(500, json={"error": "temporary"})
        return httpx.Response(200, json={"listings": []})

    adapter = _adapter(
        handler,
        marketplace_name="fake_goat",
        max_retries=1,
        headers={"Authorization": "Bearer adapter-secret"},
    )
    adapter.search_listings("sku-999")

    transport_records = [
        record for record in caplog.records if record.name == "utils.transport.logging_utils"
    ]
    assert transport_records

    payloads = [getattr(record, "transport", {}) for record in transport_records]
    assert payloads
    assert all(payload.get("marketplace_name") == "fake_goat" for payload in payloads)

    response_payloads = [payload for payload in payloads if payload.get("event") == "response_received"]
    assert response_payloads
    final = response_payloads[-1]
    assert final["response_status"] == 200
    assert final["retry_count"] == 1
    assert final["elapsed_ms"] is not None

    combined = "\n".join(record.getMessage() for record in transport_records) + str(payloads)
    assert "adapter-secret" not in combined


def test_post_mutation_flow_through_adapter() -> None:
    import json

    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json={"watchlist_id": "W-42"})

    adapter = _adapter(handler, max_retries=0)
    response = adapter.create_watchlist_entry("L-99")

    assert seen["method"] == "POST"
    assert seen["body"] == {"listing_id": "L-99"}
    assert response.status_code == 201
    assert response.json() == {"watchlist_id": "W-42"}
