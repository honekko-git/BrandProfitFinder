"""Parity validation between legacy Yahoo HTTP and Version 2 HttpTransport paths."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch

import httpx
import pytest

from marketplace.yahoo_api_client import YahooApiClient
from marketplace.yahoo_exceptions import (
    YahooApiError,
    YahooClientError,
    YahooRateLimitError,
    YahooServerError,
)
from marketplace.yahoo_marketplace import YahooMarketplace
from marketplace.yahoo_response_parser import YahooResponseParser
from marketplace.yahoo_settings import YahooApiSettings
from models.product import Product

FIXTURES = Path(__file__).parent / "fixtures"
SECRET_CLIENT_ID = "parity-test-yahoo-client-id"


def _settings(**overrides) -> YahooApiSettings:
    defaults = dict(
        client_id=SECRET_CLIENT_ID,
        base_url="https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch",
        timeout_seconds=10,
        results=20,
        enabled=True,
        use_transport=False,
        max_retries=0,
    )
    defaults.update(overrides)
    return YahooApiSettings(**defaults)


def _mock_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _legacy_client(
    handler: Callable[[httpx.Request], httpx.Response],
    **config_overrides,
) -> YahooApiClient:
    return YahooApiClient(
        settings=_settings(use_transport=False, **config_overrides),
        client=_mock_client(handler),
    )


def _transport_client(
    handler: Callable[[httpx.Request], httpx.Response],
    **config_overrides,
) -> YahooApiClient:
    return YahooApiClient(
        settings=_settings(use_transport=True, **config_overrides),
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
            "jan_code": listing.jan_code,
            "seller_name": listing.seller_name,
            "seller_rating": str(listing.seller_rating) if listing.seller_rating is not None else None,
            "shipping_jpy": str(listing.shipping_jpy),
            "brand": listing.brand,
            "marketplace_name": listing.marketplace_name,
            "availability": listing.availability,
        }
        for listing in listings
    ]


def _payload_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    hits = payload.get("hits")
    return {
        "totalResultsAvailable": payload.get("totalResultsAvailable"),
        "request": payload.get("request"),
        "hit_count": len(hits) if isinstance(hits, list) else 0,
    }


@pytest.fixture(autouse=True)
def _zero_transport_backoff(monkeypatch) -> None:
    monkeypatch.setenv("TRANSPORT_BACKOFF_BASE_SECONDS", "0")
    monkeypatch.setenv("TRANSPORT_BACKOFF_MAX_SECONDS", "0")


@pytest.mark.parametrize(
    "fixture_name",
    [
        "yahoo_item_search_success.json",
        "yahoo_item_search_partial.json",
        "yahoo_item_search_empty.json",
        "yahoo_item_search_invalid.json",
    ],
)
def test_response_payload_parity(fixture_name: str) -> None:
    payload = _fixture(fixture_name)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    legacy = _legacy_client(handler).search_items(query="gucci bag")
    transport = _transport_client(handler).search_items(query="gucci bag")

    assert legacy == transport
    assert legacy == payload
    assert _payload_metadata(legacy) == _payload_metadata(transport)


def test_parser_listing_field_parity() -> None:
    payload = _fixture("yahoo_item_search_success.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    parser = YahooResponseParser()
    legacy_payload = _legacy_client(handler).search_items(query="gucci marmont bag")
    transport_payload = _transport_client(handler).search_items(query="gucci marmont bag")

    legacy_listings = parser.parse(legacy_payload, source_query="gucci marmont bag")
    transport_listings = parser.parse(transport_payload, source_query="gucci marmont bag")

    assert _listing_snapshots(legacy_listings) == _listing_snapshots(transport_listings)
    assert len(legacy_listings) == 3
    assert legacy_listings[0].title == "Gucci Marmont Leather Bag"
    assert legacy_listings[0].price_jpy == transport_listings[0].price_jpy
    assert legacy_listings[0].listing_url == transport_listings[0].listing_url
    assert legacy_listings[0].jan_code == "4901234567890"
    assert legacy_listings[0].seller_name == "Example Store"
    assert legacy_listings[0].brand == "Gucci"


def test_marketplace_search_result_parity() -> None:
    payload = _fixture("yahoo_item_search_success.json")
    product = Product(
        name="Gucci Marmont Bag",
        brand="Gucci",
        model="GG-MARMONT",
        sku="4901234567890",
        price=600.0,
        currency="USD",
        exchange_rate=150.0,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    legacy_marketplace = YahooMarketplace(client=_legacy_client(handler))
    transport_marketplace = YahooMarketplace(client=_transport_client(handler))

    legacy_result = legacy_marketplace.search(product)
    transport_result = transport_marketplace.search(product)

    assert legacy_result.status == transport_result.status
    assert legacy_result.total_results == transport_result.total_results
    assert legacy_result.metadata == transport_result.metadata
    assert _listing_snapshots(legacy_result.listings) == _listing_snapshots(transport_result.listings)
    assert _listing_snapshots(legacy_result.valid_listings) == _listing_snapshots(
        transport_result.valid_listings
    )


def test_keyword_search_request_params_parity() -> None:
    legacy_params: dict[str, str] = {}
    transport_params: dict[str, str] = {}

    def legacy_handler(request: httpx.Request) -> httpx.Response:
        legacy_params.update(dict(request.url.params))
        return httpx.Response(200, json={"hits": []})

    def transport_handler(request: httpx.Request) -> httpx.Response:
        transport_params.update(dict(request.url.params))
        return httpx.Response(200, json={"hits": []})

    _legacy_client(legacy_handler).search_items(
        query="gucci bag",
        results=10,
        start=3,
        in_stock=True,
    )
    _transport_client(transport_handler).search_items(
        query="gucci bag",
        results=10,
        start=3,
        in_stock=True,
    )

    assert legacy_params == transport_params
    assert legacy_params["query"] == "gucci bag"
    assert legacy_params["results"] == "10"
    assert legacy_params["start"] == "3"
    assert legacy_params["in_stock"] == "true"
    assert legacy_params["appid"] == SECRET_CLIENT_ID


def test_jan_search_request_params_parity() -> None:
    legacy_params: dict[str, str] = {}
    transport_params: dict[str, str] = {}

    def legacy_handler(request: httpx.Request) -> httpx.Response:
        legacy_params.update(dict(request.url.params))
        return httpx.Response(200, json={"hits": []})

    def transport_handler(request: httpx.Request) -> httpx.Response:
        transport_params.update(dict(request.url.params))
        return httpx.Response(200, json={"hits": []})

    _legacy_client(legacy_handler).search_items(jan_code="4901234567890", start=2)
    _transport_client(transport_handler).search_items(jan_code="4901234567890", start=2)

    assert legacy_params == transport_params
    assert legacy_params["jan_code"] == "4901234567890"
    assert "query" not in legacy_params
    assert legacy_params["start"] == "2"


@pytest.mark.parametrize(
    "status,expected_type",
    [
        (400, YahooClientError),
        (401, YahooClientError),
        (403, YahooClientError),
        (404, YahooClientError),
        (429, YahooRateLimitError),
        (500, YahooServerError),
        (503, YahooServerError),
    ],
)
def test_exception_type_parity(status: int, expected_type: type[YahooApiError]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": "fail"})

    legacy_exc: Exception | None = None
    transport_exc: Exception | None = None

    try:
        _legacy_client(handler).search_items(query="bag")
    except Exception as exc:
        legacy_exc = exc

    try:
        _transport_client(handler).search_items(query="bag")
    except Exception as exc:
        transport_exc = exc

    assert legacy_exc is not None
    assert transport_exc is not None
    assert type(legacy_exc) is expected_type
    assert type(transport_exc) is expected_type
    assert type(legacy_exc) is type(transport_exc)


def test_exception_parity_no_retry_when_max_retries_zero_for_429() -> None:
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
        _legacy_client(legacy_handler, max_retries=0).search_items(query="bag")
    except Exception as exc:
        legacy_exc = exc

    try:
        _transport_client(transport_handler, max_retries=0).search_items(query="bag")
    except Exception as exc:
        transport_exc = exc

    assert isinstance(legacy_exc, YahooRateLimitError)
    assert isinstance(transport_exc, YahooRateLimitError)
    assert legacy_attempts["count"] == 1
    assert transport_attempts["count"] == 1


def test_exception_parity_no_retry_when_max_retries_zero_for_503() -> None:
    def _make_handler() -> tuple[Callable[[httpx.Request], httpx.Response], dict[str, int]]:
        attempts = {"count": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            attempts["count"] += 1
            return httpx.Response(503, json={"error": "unavailable"})

        return handler, attempts

    legacy_handler, legacy_attempts = _make_handler()
    transport_handler, transport_attempts = _make_handler()

    try:
        _legacy_client(legacy_handler, max_retries=0).search_items(query="bag")
    except Exception as exc:
        legacy_exc = exc
    else:
        legacy_exc = None

    try:
        _transport_client(transport_handler, max_retries=0).search_items(query="bag")
    except Exception as exc:
        transport_exc = exc
    else:
        transport_exc = None

    assert isinstance(legacy_exc, YahooServerError)
    assert isinstance(transport_exc, YahooServerError)
    assert legacy_attempts["count"] == 1
    assert transport_attempts["count"] == 1


def test_feature_flag_false_does_not_invoke_http_transport() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"hits": []})

    client = _legacy_client(handler)
    with patch("utils.transport.HttpTransport.get", side_effect=AssertionError("transport must not run")):
        payload = client.search_items(query="bag")

    assert payload == {"hits": []}


def test_feature_flag_true_invokes_http_transport() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"hits": []})

    client = _transport_client(handler)
    transport_calls: list[str] = []

    from utils.transport.transport import HttpTransport

    original_get = HttpTransport.get

    def _recording_get(self, url, **kwargs):
        transport_calls.append("called")
        return original_get(self, url, **kwargs)

    with patch.object(HttpTransport, "get", _recording_get):
        payload = client.search_items(query="bag")

    assert payload == {"hits": []}
    assert transport_calls == ["called"]


def test_from_env_feature_flag_defaults_false(monkeypatch) -> None:
    monkeypatch.setattr("config.settings.YAHOO_USE_TRANSPORT", False)
    settings = YahooApiSettings.from_env()
    assert settings.use_transport is False


def test_from_env_feature_flag_enabled(monkeypatch) -> None:
    monkeypatch.setattr("config.settings.YAHOO_USE_TRANSPORT", True)
    settings = YahooApiSettings.from_env()
    assert settings.use_transport is True


def test_from_env_max_retries_defaults_zero(monkeypatch) -> None:
    monkeypatch.setattr("config.settings.YAHOO_API_MAX_RETRIES", 0)
    settings = YahooApiSettings.from_env()
    assert settings.max_retries == 0


def test_logging_security_appid_not_exposed_on_transport_path(caplog) -> None:
    caplog.set_level(logging.INFO, logger="utils.transport.logging_utils")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"hits": []})

    client = _transport_client(handler)
    client.search_items(query="bag")

    transport_records = [
        record for record in caplog.records if record.name == "utils.transport.logging_utils"
    ]
    combined = "\n".join(record.getMessage() for record in transport_records)
    for record in transport_records:
        combined += str(getattr(record, "transport", {}))
    assert SECRET_CLIENT_ID not in combined
