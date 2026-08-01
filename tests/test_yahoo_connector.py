"""Tests for Yahoo Auction live connector price parsing."""

from __future__ import annotations

from decimal import Decimal

import pytest

from marketplace.connectors.config import MarketConnectorConfig
from marketplace.connectors.live.exceptions import MarketConnectorParseError
from marketplace.connectors.live.http_client import MarketHttpClient
from marketplace.connectors.live.yahoo.connector import YahooAuctionLiveConnector
from marketplace.connectors.live.yahoo.parser import parse_yahoo_auction_response


class _FakeHttpClient(MarketHttpClient):
    def __init__(self, payload: dict) -> None:
        super().__init__(retry_count=0)
        self._payload = payload

    def get_json(self, url: str, *, params: dict[str, str] | None = None) -> dict:
        return self._payload


def test_parse_yahoo_auction_response_parses_price_jpy() -> None:
    listings = parse_yahoo_auction_response(
        {
            "listings": [
                {
                    "listing_id": "ya-001",
                    "title": "Chanel Wallet",
                    "brand": "Chanel",
                    "category": "wallet",
                    "condition": "used",
                    "price_jpy": 150000,
                    "url": "https://example.invalid/ya-001",
                }
            ]
        }
    )

    assert len(listings) == 1
    listing = listings[0]
    assert listing.price == Decimal("150000")
    assert listing.currency == "JPY"
    assert listing.market_name == "Yahoo Auction"


def test_parse_yahoo_auction_response_accepts_price_alias() -> None:
    listings = parse_yahoo_auction_response(
        {
            "listings": [
                {
                    "listing_id": "ya-002",
                    "title": "Gucci Bag",
                    "brand": "Gucci",
                    "price": 88000,
                    "url": "https://example.invalid/ya-002",
                }
            ]
        }
    )

    assert listings[0].price == Decimal("88000")


def test_parse_yahoo_auction_response_requires_listings_array() -> None:
    with pytest.raises(MarketConnectorParseError):
        parse_yahoo_auction_response({"items": []})


def test_yahoo_connector_search_products_returns_parsed_listings() -> None:
    connector = YahooAuctionLiveConnector(
        config=MarketConnectorConfig(yahoo_auction_api_url="https://example.invalid/yahoo"),
        http_client=_FakeHttpClient(
            {
                "listings": [
                    {
                        "listing_id": "ya-live-1",
                        "title": "Chanel Classic Wallet",
                        "brand": "Chanel",
                        "price_jpy": 165000,
                        "url": "https://example.invalid/ya-live-1",
                    }
                ]
            }
        ),
    )

    listings = connector.search_products("Chanel Wallet")

    assert len(listings) == 1
    assert listings[0].price == Decimal("165000")
