"""Unit tests for marketplace.yahoo_auction_marketplace."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from config.constants import MARKETPLACE_YAHOO_AUCTION
from marketplace.yahoo_auction_client import FakeYahooAuctionClient
from marketplace.yahoo_auction_exceptions import YahooAuctionResponseError
from marketplace.yahoo_auction_marketplace import YahooAuctionMarketplace
from marketplace.yahoo_auction_response_parser import YahooAuctionResponseParser
from marketplace.yahoo_auction_settings import YahooAuctionConfig
from models.marketplace_search_result import SEARCH_ERROR, SEARCH_NO_LISTINGS, SEARCH_SUCCESS
from models.product import Product

FIXTURES = Path(__file__).parent / "fixtures"


def _config(**overrides) -> YahooAuctionConfig:
    defaults = dict(
        enabled=True,
        demo_enabled=True,
        data_source="",
        timeout_seconds=10,
        max_retries=0,
        hits=20,
        sort="end_time",
    )
    defaults.update(overrides)
    return YahooAuctionConfig(**defaults)


def _payload(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _product(**kwargs) -> Product:
    defaults = dict(
        name="Gucci Marmont Wallet",
        brand="GUCCI",
        model="428726",
        sku="428726",
        price=600.0,
        currency="USD",
        exchange_rate=150.0,
    )
    defaults.update(kwargs)
    return Product(**defaults)


def _marketplace(name: str = "yahoo_auction_search_multiple.json") -> YahooAuctionMarketplace:
    return YahooAuctionMarketplace(
        client=FakeYahooAuctionClient(_payload(name)),
        config=_config(),
    )


def test_client_called() -> None:
    client = FakeYahooAuctionClient(_payload("yahoo_auction_search_normal.json"))
    marketplace = YahooAuctionMarketplace(client=client, config=_config())
    marketplace.search(_product())
    assert client.last_query == "GUCCI 428726"


def test_search_query_jan_priority() -> None:
    client = FakeYahooAuctionClient(_payload("yahoo_auction_search_empty.json"))
    marketplace = YahooAuctionMarketplace(client=client, config=_config())
    marketplace.search(_product(sku="4901234567890", model="428726"))
    assert client.last_query == "4901234567890"


def test_search_query_override() -> None:
    client = FakeYahooAuctionClient(_payload("yahoo_auction_search_empty.json"))
    marketplace = YahooAuctionMarketplace(client=client, config=_config())
    marketplace.search(_product(), query="custom query")
    assert client.last_query == "custom query"


def test_parser_results_returned() -> None:
    result = _marketplace().search(_product())
    assert len(result.listings) == 3
    assert result.marketplace_name == MARKETPLACE_YAHOO_AUCTION


def test_empty_results() -> None:
    result = _marketplace("yahoo_auction_search_empty.json").search(_product())
    assert result.status == SEARCH_NO_LISTINGS


def test_client_exception() -> None:
    client = FakeYahooAuctionClient(error=RuntimeError("client failure"))
    result = YahooAuctionMarketplace(client=client, config=_config()).search(_product())
    assert result.status == SEARCH_ERROR


def test_parser_exception(monkeypatch) -> None:
    client = FakeYahooAuctionClient({"items": "bad"})

    def broken_validate(payload):
        raise YahooAuctionResponseError("bad payload")

    monkeypatch.setattr(YahooAuctionResponseParser, "validate_payload", staticmethod(broken_validate))
    result = YahooAuctionMarketplace(client=client, config=_config()).search(_product())
    assert result.status == SEARCH_ERROR


def test_no_client_configured() -> None:
    result = YahooAuctionMarketplace(client=None, config=_config()).search(_product())
    assert result.status == SEARCH_ERROR
    assert "not configured" in (result.error_message or "")


def test_hits_passed_to_client() -> None:
    client = FakeYahooAuctionClient(_payload("yahoo_auction_search_empty.json"))
    marketplace = YahooAuctionMarketplace(client=client, config=_config(hits=10))
    marketplace.search(_product())
    assert client.last_hits == 10


def test_page_metadata() -> None:
    result = _marketplace().search(_product())
    assert result.total_results == 3
    assert result.next_page_token == "2"
    assert result.metadata["has_next_page"] is True


def test_demo_fixture_success() -> None:
    result = _marketplace("yahoo_auction_search_normal.json").search(_product())
    assert result.status == SEARCH_SUCCESS
    assert result.selected_price_jpy == Decimal("108000")
