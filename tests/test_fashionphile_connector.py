"""Tests for Fashionphile live connector parser and listing conversion."""

from __future__ import annotations

from decimal import Decimal

import pytest

from marketplace.connectors.config import MarketConnectorConfig
from marketplace.connectors.live.exceptions import MarketConnectorParseError
from marketplace.connectors.live.fashionphile.connector import FashionphileLiveConnector
from marketplace.connectors.live.fashionphile.parser import parse_fashionphile_response
from marketplace.connectors.live.http_client import MarketHttpClient


class _FakeHttpClient(MarketHttpClient):
    def __init__(self, payload: dict) -> None:
        super().__init__(retry_count=0)
        self._payload = payload

    def get_json(self, url: str, *, params: dict[str, str] | None = None) -> dict:
        return self._payload


def test_parse_fashionphile_response_converts_listings() -> None:
    listings = parse_fashionphile_response(
        {
            "items": [
                {
                    "listing_id": "fp-001",
                    "title": "Chanel Classic Wallet",
                    "brand": "Chanel",
                    "category": "wallet",
                    "condition": {"raw": "Excellent"},
                    "price": {"amount": 1200, "currency": "USD"},
                    "url": "https://example.invalid/fp-001",
                }
            ]
        }
    )

    assert len(listings) == 1
    listing = listings[0]
    assert listing.id == "fp-001"
    assert listing.title == "Chanel Classic Wallet"
    assert listing.brand == "Chanel"
    assert listing.category == "wallet"
    assert listing.condition == "Excellent"
    assert listing.price == Decimal("1200")
    assert listing.currency == "USD"
    assert listing.market_name == "Fashionphile"
    assert listing.url == "https://example.invalid/fp-001"
    assert listing.source_type == "LIVE"


def test_parse_fashionphile_response_requires_items_array() -> None:
    with pytest.raises(MarketConnectorParseError):
        parse_fashionphile_response({"results": []})


def test_fashionphile_connector_search_products_uses_parser() -> None:
    connector = FashionphileLiveConnector(
        config=MarketConnectorConfig(fashionphile_api_url="https://example.invalid/fashionphile"),
        http_client=_FakeHttpClient(
            {
                "items": [
                    {
                        "listing_id": "fp-live-1",
                        "title": "Louis Vuitton Speedy",
                        "brand": "Louis Vuitton",
                        "category": "bag",
                        "condition": "Good",
                        "price": {"amount": 900, "currency": "USD"},
                        "url": "https://example.invalid/fp-live-1",
                    }
                ]
            }
        ),
    )

    listings = connector.search_products("Louis Vuitton")

    assert len(listings) == 1
    assert listings[0].market_name == "Fashionphile"
    assert connector.get_product("https://example.invalid/fp-live-1") is listings[0]
