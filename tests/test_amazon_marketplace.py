"""Unit tests for marketplace.amazon_marketplace."""

import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest

from config.constants import MARKETPLACE_AMAZON_JP
from marketplace.amazon_client import FakeAmazonClient
from marketplace.amazon_exceptions import AmazonResponseParseError
from marketplace.amazon_marketplace import AmazonMarketplace
from marketplace.amazon_response_parser import AmazonResponseParser
from marketplace.amazon_settings import AmazonConfig
from models.marketplace_search_result import SEARCH_ERROR, SEARCH_NO_LISTINGS, SEARCH_SUCCESS
from models.product import Product

FIXTURES = Path(__file__).parent / "fixtures"


def _config(**overrides) -> AmazonConfig:
    defaults = dict(
        marketplace_id="A1VC38T7YXB528",
        default_currency="JPY",
        default_language="ja_JP",
        max_results=20,
        timeout_seconds=10,
        retry_count=0,
        enabled=True,
        demo_enabled=True,
    )
    defaults.update(overrides)
    return AmazonConfig(**defaults)


def _payload(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _product(**kwargs) -> Product:
    defaults = dict(
        name="Gucci Marmont Wallet",
        brand="GUCCI",
        model="456126",
        sku="456126",
        price=600.0,
        currency="USD",
        exchange_rate=150.0,
    )
    defaults.update(kwargs)
    return Product(**defaults)


def _marketplace(name: str = "amazon_search_multiple.json") -> AmazonMarketplace:
    client = FakeAmazonClient(_payload(name))
    return AmazonMarketplace(client=client, config=_config())


def test_client_called() -> None:
    client = FakeAmazonClient(_payload("amazon_search_normal.json"))
    marketplace = AmazonMarketplace(client=client, config=_config())
    marketplace.search(_product())
    assert client.last_query == "GUCCI 456126"


def test_search_query_passed() -> None:
    client = FakeAmazonClient(_payload("amazon_search_empty.json"))
    marketplace = AmazonMarketplace(client=client, config=_config())
    marketplace.search(_product(), query="custom query")
    assert client.last_query == "custom query"


def test_parser_results_returned() -> None:
    result = _marketplace().search(_product())
    assert len(result.listings) == 3
    assert result.marketplace_name == MARKETPLACE_AMAZON_JP


def test_empty_results() -> None:
    result = _marketplace("amazon_search_empty.json").search(_product())
    assert result.status == SEARCH_NO_LISTINGS


def test_client_exception() -> None:
    class BrokenClient(FakeAmazonClient):
        def search_items(self, **kwargs):
            raise RuntimeError("client failure")

    marketplace = AmazonMarketplace(client=BrokenClient({}), config=_config())
    result = marketplace.search(_product())
    assert result.status == SEARCH_ERROR


def test_parser_exception(monkeypatch) -> None:
    client = FakeAmazonClient({"items": "bad"})

    def broken_validate(payload):
        raise AmazonResponseParseError("bad payload")

    monkeypatch.setattr(AmazonResponseParser, "validate_payload", staticmethod(broken_validate))
    result = AmazonMarketplace(client=client, config=_config()).search(_product())
    assert result.status == SEARCH_ERROR


def test_page_metadata() -> None:
    result = _marketplace().search(_product())
    assert result.total_results == 3
    assert result.next_page_token == "page-2-token"


def test_max_results_passed() -> None:
    client = FakeAmazonClient(_payload("amazon_search_empty.json"))
    marketplace = AmazonMarketplace(client=client, config=_config(max_results=5))
    marketplace.search(_product())
    assert client.last_max_results == 5


def test_no_client_configured() -> None:
    result = AmazonMarketplace(client=None, config=_config()).search(_product())
    assert result.status == SEARCH_ERROR
    assert "not configured" in (result.error_message or "")


def test_product_not_mutated() -> None:
    product = _product()
    original = deepcopy(product)
    _marketplace().search(product)
    assert product == original


def test_valid_candidates_and_match_scores() -> None:
    result = _marketplace().search(_product())
    assert result.status == SEARCH_SUCCESS
    assert any(item.match_score > 0 for item in result.valid_listings)


def test_selected_price() -> None:
    result = _marketplace().search(_product())
    assert result.selected_price_jpy == Decimal("198500")


def test_deterministic_results() -> None:
    marketplace = _marketplace()
    first = marketplace.search(_product())
    second = marketplace.search(_product())
    assert [item.listing_id for item in first.valid_listings] == [item.listing_id for item in second.valid_listings]
