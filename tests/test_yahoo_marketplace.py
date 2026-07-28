"""Unit tests for marketplace.yahoo_marketplace."""

import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from config.constants import MARKETPLACE_YAHOO
from marketplace.base_marketplace import BaseMarketplace
from marketplace.yahoo_api_client import YahooApiClient
from marketplace.yahoo_exceptions import YahooClientError, YahooConfigError
from marketplace.yahoo_marketplace import YahooMarketplace, _extract_jan_code, _normalize_query
from marketplace.yahoo_settings import YahooApiSettings
from models.marketplace_search_result import SEARCH_ERROR, SEARCH_NO_LISTINGS, SEARCH_SUCCESS
from models.product import Product
from price_compare.price_comparator import PriceSelectionStrategy

FIXTURES = Path(__file__).parent / "fixtures"
DUMMY_CLIENT_ID = "dummy-test-client-id"


def _settings(**overrides) -> YahooApiSettings:
    defaults = dict(
        client_id=DUMMY_CLIENT_ID,
        base_url="https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch",
        timeout_seconds=10,
        results=20,
        enabled=True,
    )
    defaults.update(overrides)
    return YahooApiSettings(**defaults)


def _payload(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _marketplace(payload: dict) -> YahooMarketplace:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = YahooApiClient(settings=_settings(), client=httpx.Client(transport=httpx.MockTransport(handler)))
    return YahooMarketplace(client=client)


def _product(**kwargs) -> Product:
    defaults = dict(
        name="Gucci Marmont Bag",
        brand="Gucci",
        model="GG-MARMONT",
        sku="4901234567890",
        price=600.0,
        currency="USD",
        exchange_rate=150.0,
    )
    defaults.update(kwargs)
    return Product(**defaults)


def test_inherits_base_marketplace() -> None:
    marketplace = _marketplace(_payload("yahoo_item_search_success.json"))
    assert isinstance(marketplace, BaseMarketplace)


def test_marketplace_name() -> None:
    marketplace = _marketplace(_payload("yahoo_item_search_success.json"))
    assert marketplace.marketplace_name == MARKETPLACE_YAHOO


def test_jan_search_priority() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_payload("yahoo_item_search_success.json"))

    client = YahooApiClient(settings=_settings(), client=httpx.Client(transport=httpx.MockTransport(handler)))
    marketplace = YahooMarketplace(client=client)
    marketplace.search(_product())

    assert captured["params"]["jan_code"] == "4901234567890"
    assert "query" not in captured["params"]


def test_query_search_without_jan() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_payload("yahoo_item_search_success.json"))

    client = YahooApiClient(settings=_settings(), client=httpx.Client(transport=httpx.MockTransport(handler)))
    marketplace = YahooMarketplace(client=client)
    marketplace.search(_product(sku="P3-001"))

    assert captured["params"]["query"] == "Gucci GG-MARMONT"


def test_brand_and_name_query() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"hits": []})

    client = YahooApiClient(settings=_settings(), client=httpx.Client(transport=httpx.MockTransport(handler)))
    marketplace = YahooMarketplace(client=client)
    marketplace.search(_product(model="", sku="SKU-1"))

    assert captured["params"]["query"] == "Gucci Gucci Marmont Bag"


def test_whitespace_normalization() -> None:
    assert _normalize_query("  Gucci   Bag  ") == "Gucci Bag"


def test_search_returns_marketplace_search_result() -> None:
    result = _marketplace(_payload("yahoo_item_search_success.json")).search(_product())
    assert result.marketplace_name == MARKETPLACE_YAHOO
    assert result.query


def test_zero_candidates() -> None:
    result = _marketplace(_payload("yahoo_item_search_empty.json")).search(_product())
    assert result.status == SEARCH_NO_LISTINGS


def test_valid_candidates() -> None:
    result = _marketplace(_payload("yahoo_item_search_success.json")).search(_product())
    assert result.status == SEARCH_SUCCESS
    assert len(result.valid_listings) >= 2


def test_partial_invalid_candidates() -> None:
    result = _marketplace(_payload("yahoo_item_search_partial.json")).search(_product(sku="SKU-1"))
    assert len(result.rejected_listings) >= 1
    assert len(result.valid_listings) >= 1


def test_match_score_set() -> None:
    result = _marketplace(_payload("yahoo_item_search_success.json")).search(_product())
    assert all(item.match_score >= 0 for item in result.valid_listings)


def test_ranked_by_score() -> None:
    result = _marketplace(_payload("yahoo_item_search_success.json")).search(_product())
    scores = [item.match_score for item in result.valid_listings]
    assert scores == sorted(scores, reverse=True)


def test_product_not_mutated() -> None:
    product = _product()
    original = deepcopy(product)
    _marketplace(_payload("yahoo_item_search_success.json")).search(product)
    assert product == original


def test_api_error_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "server"})

    client = YahooApiClient(settings=_settings(), client=httpx.Client(transport=httpx.MockTransport(handler)))
    result = YahooMarketplace(client=client).search(_product())
    assert result.status == SEARCH_ERROR
    assert result.error_message


def test_config_error_result() -> None:
    client = YahooApiClient(settings=_settings(client_id=""))
    result = YahooMarketplace(client=client).search(_product())
    assert result.status == SEARCH_ERROR
    assert "Client ID" in (result.error_message or "")


def test_deterministic_results() -> None:
    marketplace = _marketplace(_payload("yahoo_item_search_success.json"))
    first = marketplace.search(_product())
    second = marketplace.search(_product())
    assert [item.listing_id for item in first.valid_listings] == [item.listing_id for item in second.valid_listings]


def test_no_network_access() -> None:
    marketplace = _marketplace(_payload("yahoo_item_search_success.json"))
    with patch("utils.http.fetch_url") as mock_fetch, patch("utils.http.HttpClient") as mock_client:
        marketplace.search(_product())
    mock_fetch.assert_not_called()
    mock_client.assert_not_called()


def test_extract_jan_from_sku() -> None:
    product = Product(sku="0123456789012")
    assert _extract_jan_code(product) == "0123456789012"


def test_selected_price_highest_strategy() -> None:
    marketplace = YahooMarketplace(
        client=_marketplace(_payload("yahoo_item_search_success.json"))._client,
        selection_strategy=PriceSelectionStrategy.HIGHEST,
    )
    result = marketplace.search(_product())
    assert result.selected_price_jpy == Decimal("102000")
