"""Parity validation between legacy Rakuten HTTP and Version 2 HttpTransport paths."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch

import httpx
import pytest

from marketplace.rakuten_client import RakutenApiClient
from marketplace.rakuten_exceptions import (
    RakutenApiError,
    RakutenMarketplaceError,
    RakutenNotFoundError,
    RakutenRateLimitError,
    RakutenServerError,
    RakutenServiceUnavailableError,
)
from marketplace.rakuten_marketplace import RakutenMarketplace
from marketplace.rakuten_response_parser import RakutenResponseParser
from marketplace.rakuten_settings import RakutenConfig
from models.product import Product

FIXTURES = Path(__file__).parent / "fixtures"
SECRET_KEY = "parity-test-access-key"


def _config(**overrides) -> RakutenConfig:
    defaults = dict(
        application_id="dummy-app-id",
        access_key=SECRET_KEY,
        affiliate_id="aff-optional",
        base_url="https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701",
        timeout_seconds=10,
        max_retries=0,
        hits=20,
        sort="standard",
        enabled=True,
        demo_enabled=False,
        use_transport=False,
    )
    defaults.update(overrides)
    return RakutenConfig(**defaults)


def _mock_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _legacy_client(
    handler: Callable[[httpx.Request], httpx.Response],
    **config_overrides,
) -> RakutenApiClient:
    return RakutenApiClient(
        settings=_config(use_transport=False, **config_overrides),
        client=_mock_client(handler),
    )


def _transport_client(
    handler: Callable[[httpx.Request], httpx.Response],
    **config_overrides,
) -> RakutenApiClient:
    return RakutenApiClient(
        settings=_config(use_transport=True, **config_overrides),
        client=_mock_client(handler),
    )


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _listing_snapshots(listings) -> list[dict[str, Any]]:
    return [
        {
            "title": listing.title,
            "price_jpy": str(listing.price_jpy),
            "listing_url": listing.listing_url,
            "listing_id": listing.listing_id,
            "sku": listing.sku,
            "marketplace_name": listing.marketplace_name,
        }
        for listing in listings
    ]


@pytest.fixture(autouse=True)
def _zero_transport_backoff(monkeypatch) -> None:
    monkeypatch.setenv("TRANSPORT_BACKOFF_BASE_SECONDS", "0")
    monkeypatch.setenv("TRANSPORT_BACKOFF_MAX_SECONDS", "0")


@pytest.mark.parametrize(
    "fixture_name",
    [
        "rakuten_search_normal.json",
        "rakuten_search_multiple.json",
        "rakuten_search_empty.json",
    ],
)
def test_response_payload_parity(fixture_name: str) -> None:
    payload = _fixture(fixture_name)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    legacy = _legacy_client(handler).search_items(keyword="gucci wallet")
    transport = _transport_client(handler).search_items(keyword="gucci wallet")

    assert legacy == transport
    assert legacy == payload


def test_parser_listing_and_metadata_parity() -> None:
    payload = _fixture("rakuten_search_multiple.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    parser = RakutenResponseParser()
    legacy_payload = _legacy_client(handler).search_items(keyword="gucci")
    transport_payload = _transport_client(handler).search_items(keyword="gucci")

    legacy_listings = parser.parse(legacy_payload, source_query="gucci")
    transport_listings = parser.parse(transport_payload, source_query="gucci")
    legacy_meta = parser.parse_metadata(legacy_payload)
    transport_meta = parser.parse_metadata(transport_payload)

    assert _listing_snapshots(legacy_listings) == _listing_snapshots(transport_listings)
    assert len(legacy_listings) == 3
    assert legacy_meta == transport_meta
    assert legacy_meta["count"] == 3
    assert legacy_meta["page"] == 1
    assert legacy_meta["page_count"] == 2
    assert legacy_meta["has_next_page"] is True
    assert legacy_meta["next_page"] == "2"


def test_marketplace_search_result_parity() -> None:
    payload = _fixture("rakuten_search_multiple.json")
    product = Product(
        name="Gucci Marmont Wallet",
        brand="GUCCI",
        model="456126",
        sku="456126",
        price=600.0,
        currency="USD",
        exchange_rate=150.0,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    legacy_marketplace = RakutenMarketplace(
        client=_legacy_client(handler),
        config=_config(use_transport=False),
    )
    transport_marketplace = RakutenMarketplace(
        client=_transport_client(handler),
        config=_config(use_transport=True),
    )

    legacy_result = legacy_marketplace.search(product)
    transport_result = transport_marketplace.search(product)

    assert legacy_result.status == transport_result.status
    assert legacy_result.total_results == transport_result.total_results
    assert legacy_result.metadata == transport_result.metadata
    assert _listing_snapshots(legacy_result.listings) == _listing_snapshots(transport_result.listings)
    assert _listing_snapshots(legacy_result.valid_listings) == _listing_snapshots(
        transport_result.valid_listings
    )


@pytest.mark.parametrize(
    "status,expected_type",
    [
        (404, RakutenNotFoundError),
        (429, RakutenRateLimitError),
        (401, RakutenApiError),
        (403, RakutenApiError),
        (500, RakutenServerError),
        (503, RakutenServiceUnavailableError),
    ],
)
def test_exception_type_parity(status: int, expected_type: type[RakutenMarketplaceError]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": "fail"})

    legacy_exc: Exception | None = None
    transport_exc: Exception | None = None

    try:
        _legacy_client(handler).search_items(keyword="bag")
    except Exception as exc:
        legacy_exc = exc

    try:
        _transport_client(handler).search_items(keyword="bag")
    except Exception as exc:
        transport_exc = exc

    assert legacy_exc is not None
    assert transport_exc is not None
    assert type(legacy_exc) is expected_type
    assert type(transport_exc) is expected_type
    assert type(legacy_exc) is type(transport_exc)


def test_exception_parity_after_retry_exhaustion_for_429() -> None:
    def _make_handler() -> tuple[Callable[[httpx.Request], httpx.Response], dict[str, int]]:
        attempts = {"count": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            attempts["count"] += 1
            return httpx.Response(429, json={"error": "rate limit"})

        return handler, attempts

    legacy_handler, legacy_attempts = _make_handler()
    transport_handler, transport_attempts = _make_handler()

    legacy_exc: Exception | None = None
    transport_exc: Exception | None = None

    try:
        _legacy_client(legacy_handler, max_retries=2).search_items(keyword="bag")
    except Exception as exc:
        legacy_exc = exc

    try:
        _transport_client(transport_handler, max_retries=2).search_items(keyword="bag")
    except Exception as exc:
        transport_exc = exc

    assert isinstance(legacy_exc, RakutenRateLimitError)
    assert isinstance(transport_exc, RakutenRateLimitError)
    assert legacy_attempts["count"] == 3
    assert transport_attempts["count"] == 3


def test_exception_parity_after_retry_exhaustion_for_503() -> None:
    def _make_handler() -> tuple[Callable[[httpx.Request], httpx.Response], dict[str, int]]:
        attempts = {"count": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            attempts["count"] += 1
            return httpx.Response(503, json={"error": "unavailable"})

        return handler, attempts

    legacy_handler, legacy_attempts = _make_handler()
    transport_handler, transport_attempts = _make_handler()

    try:
        _legacy_client(legacy_handler, max_retries=2).search_items(keyword="bag")
    except Exception as exc:
        legacy_exc = exc
    else:
        legacy_exc = None

    try:
        _transport_client(transport_handler, max_retries=2).search_items(keyword="bag")
    except Exception as exc:
        transport_exc = exc
    else:
        transport_exc = None

    assert isinstance(legacy_exc, RakutenServiceUnavailableError)
    assert isinstance(transport_exc, RakutenServiceUnavailableError)
    assert legacy_attempts["count"] == 3
    assert transport_attempts["count"] == 3


def test_feature_flag_false_does_not_invoke_http_transport() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"Items": []})

    client = _legacy_client(handler)
    with patch("utils.transport.HttpTransport.get", side_effect=AssertionError("transport must not run")):
        payload = client.search_items(keyword="bag")

    assert payload == {"Items": []}


def test_feature_flag_true_invokes_http_transport() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"Items": []})

    client = _transport_client(handler)
    transport_calls: list[str] = []

    from utils.transport.transport import HttpTransport

    original_get = HttpTransport.get

    def _recording_get(self, url, **kwargs):
        transport_calls.append("called")
        return original_get(self, url, **kwargs)

    with patch.object(HttpTransport, "get", _recording_get):
        payload = client.search_items(keyword="bag")

    assert payload == {"Items": []}
    assert transport_calls == ["called"]


def test_from_env_feature_flag_defaults_false(monkeypatch) -> None:
    monkeypatch.setattr("config.settings.RAKUTEN_USE_TRANSPORT", False)
    config = RakutenConfig.from_env()
    assert config.use_transport is False


def test_from_env_feature_flag_enabled(monkeypatch) -> None:
    monkeypatch.setattr("config.settings.RAKUTEN_USE_TRANSPORT", True)
    config = RakutenConfig.from_env()
    assert config.use_transport is True
