"""Production-readiness validation for Yahoo Shopping with YAHOO_USE_TRANSPORT enabled."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from config import settings
from marketplace.marketplace_factory import create_marketplace
from marketplace.yahoo_api_client import YahooApiClient
from marketplace.yahoo_marketplace import YahooMarketplace, create_yahoo_marketplace
from marketplace.yahoo_response_parser import YahooResponseParser
from marketplace.yahoo_settings import YahooApiSettings
from models.marketplace_search_result import SEARCH_SUCCESS
from models.product import Product
from price_compare.price_comparator import PriceComparator, PriceSelectionStrategy

FIXTURES = Path(__file__).parent / "fixtures"
SECRET_CLIENT_ID = "live-validation-yahoo-client-id"


def _transport_settings(**overrides) -> YahooApiSettings:
    defaults = dict(
        client_id=SECRET_CLIENT_ID,
        base_url="https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch",
        timeout_seconds=10,
        results=20,
        enabled=True,
        use_transport=True,
        max_retries=0,
    )
    defaults.update(overrides)
    return YahooApiSettings(**defaults)


def _mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _product() -> Product:
    return Product(
        name="Gucci Marmont Bag",
        brand="Gucci",
        model="GG-MARMONT",
        sku="4901234567890",
        price=600.0,
        currency="USD",
        exchange_rate=150.0,
    )


@pytest.fixture(autouse=True)
def _zero_transport_backoff(monkeypatch) -> None:
    monkeypatch.setenv("TRANSPORT_BACKOFF_BASE_SECONDS", "0")
    monkeypatch.setenv("TRANSPORT_BACKOFF_MAX_SECONDS", "0")


def test_environment_flag_loads_use_transport_true(monkeypatch) -> None:
    monkeypatch.setenv("YAHOO_USE_TRANSPORT", "true")
    monkeypatch.setattr(settings, "YAHOO_USE_TRANSPORT", True)

    config = YahooApiSettings.from_env()

    assert config.use_transport is True


def test_environment_flag_loads_use_transport_false_by_default(monkeypatch) -> None:
    monkeypatch.delenv("YAHOO_USE_TRANSPORT", raising=False)
    monkeypatch.setattr(settings, "YAHOO_USE_TRANSPORT", False)

    config = YahooApiSettings.from_env()

    assert config.use_transport is False


def test_factory_flow_uses_transport_enabled_api_client() -> None:
    payload = json.loads((FIXTURES / "yahoo_item_search_success.json").read_text(encoding="utf-8"))
    transport_calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    config = _transport_settings()
    api_client = YahooApiClient(settings=config, client=_mock_client(handler))
    marketplace = create_yahoo_marketplace(settings=config, client=api_client)

    assert isinstance(marketplace, YahooMarketplace)
    assert marketplace._client.settings.use_transport is True
    assert isinstance(marketplace._client, YahooApiClient)

    from utils.transport.transport import HttpTransport

    original_get = HttpTransport.get

    def _recording_get(self, url, **kwargs):
        transport_calls.append("called")
        return original_get(self, url, **kwargs)

    with patch.object(HttpTransport, "get", _recording_get):
        result = marketplace.search(_product())

    assert transport_calls == ["called"]
    assert result.status == SEARCH_SUCCESS
    assert result.selected_listing is not None


def test_create_marketplace_yahoo_factory_with_transport_client() -> None:
    payload = json.loads((FIXTURES / "yahoo_item_search_success.json").read_text(encoding="utf-8"))
    transport_calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    config = _transport_settings()
    api_client = YahooApiClient(settings=config, client=_mock_client(handler))

    with patch.object(YahooApiClient, "from_settings", return_value=api_client):
        marketplace = create_marketplace("yahoo", yahoo_settings=config)

    assert isinstance(marketplace, YahooMarketplace)
    assert marketplace._client is api_client
    assert marketplace._client.settings.use_transport is True

    from utils.transport.transport import HttpTransport

    original_get = HttpTransport.get

    def _recording_get(self, url, **kwargs):
        transport_calls.append("called")
        return original_get(self, url, **kwargs)

    with patch.object(HttpTransport, "get", _recording_get):
        result = marketplace.search(_product())

    assert transport_calls == ["called"]
    assert result.status == SEARCH_SUCCESS


def test_create_marketplace_yahoo_settings_propagate_use_transport() -> None:
    config = _transport_settings()
    marketplace = create_marketplace("yahoo", yahoo_settings=config)

    assert isinstance(marketplace, YahooMarketplace)
    assert isinstance(marketplace._client, YahooApiClient)
    assert marketplace._client.settings.use_transport is True
    assert marketplace._client.settings.max_retries == 0


def test_search_pipeline_transport_parser_and_result_metadata() -> None:
    payload = json.loads((FIXTURES / "yahoo_item_search_success.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    config = _transport_settings()
    marketplace = YahooMarketplace(
        client=YahooApiClient(settings=config, client=_mock_client(handler)),
    )

    result = marketplace.search(_product())
    parser = YahooResponseParser()
    parsed = parser.parse(payload, source_query=result.query)

    assert result.status == SEARCH_SUCCESS
    assert result.query == "4901234567890"
    assert len(result.listings) == len(parsed) == 3
    assert len(result.valid_listings) >= 1
    assert result.listings[0].title
    assert result.listings[0].price_jpy is not None
    assert result.listings[0].listing_url.startswith("https://")
    assert result.listings[0].seller_name
    assert result.listings[0].brand == "Gucci"
    assert payload["totalResultsAvailable"] == 3


def test_search_pipeline_ranking_compatibility_with_transport() -> None:
    payload = json.loads((FIXTURES / "yahoo_item_search_success.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    config = _transport_settings()
    marketplace = YahooMarketplace(
        client=YahooApiClient(settings=config, client=_mock_client(handler)),
    )

    result = marketplace.search(_product())
    comparator = PriceComparator()

    highest = comparator.select_from_listings(
        result.valid_listings,
        strategy=PriceSelectionStrategy.HIGHEST,
    )
    lowest = comparator.select_from_listings(
        result.valid_listings,
        strategy=PriceSelectionStrategy.LOWEST,
    )

    assert highest is not None
    assert lowest is not None
    assert result.selected_price_jpy == highest[1]
    assert highest[1] >= lowest[1]
    assert len(result.valid_listings) >= 2


def test_retry_max_retries_zero_preserves_single_request() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(429, json={"error": "rate limit"})

    config = _transport_settings(max_retries=0)
    marketplace = YahooMarketplace(
        client=YahooApiClient(settings=config, client=_mock_client(handler)),
    )

    result = marketplace.search(_product())

    assert attempts["count"] == 1
    assert result.status == "error"


def test_logging_security_transport_enabled_full_pipeline(caplog) -> None:
    caplog.set_level(logging.INFO)

    payload = json.loads((FIXTURES / "yahoo_item_search_success.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    config = _transport_settings()
    marketplace = YahooMarketplace(
        client=YahooApiClient(settings=config, client=_mock_client(handler)),
    )
    marketplace.search(_product())

    transport_records = [
        record for record in caplog.records if record.name == "utils.transport.logging_utils"
    ]
    assert transport_records
    combined = "\n".join(record.getMessage() for record in transport_records)
    for record in transport_records:
        combined += str(getattr(record, "transport", {}))

    assert SECRET_CLIENT_ID not in combined
