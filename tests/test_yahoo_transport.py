"""Tests for Yahoo Auction live transport and parsing."""

from __future__ import annotations

import pytest

from marketplace.domestic_market.yahoo_auction import (
    FakeYahooAuctionTransport,
    YahooAuctionLiveUnavailableError,
    YahooAuctionTransport,
    calculate_average_price,
    parse_sold_items,
    to_market_price_data,
)


def test_yahoo_transport_protocol_is_runtime_checkable() -> None:
    transport = FakeYahooAuctionTransport()

    assert isinstance(transport, YahooAuctionTransport)


def test_fake_yahoo_transport_returns_sold_items() -> None:
    transport = FakeYahooAuctionTransport(
        items_by_query={
            "chanel wallet": [
                {
                    "title": "Chanel Classic Wallet",
                    "sold_price": 150000,
                    "url": "https://example.invalid/chanel-wallet",
                    "sold_date": "2026-07-01",
                }
            ]
        }
    )

    items = transport.search_sold_items("Chanel Wallet")

    assert len(items) == 1
    assert items[0]["title"] == "Chanel Classic Wallet"
    assert items[0]["sold_price"] == 150000


def test_parse_sold_items_normalizes_transport_payload() -> None:
    parsed = parse_sold_items(
        [
            {
                "title": "Louis Vuitton Wallet",
                "sold_price": 120000,
                "url": "https://example.invalid/lv-wallet",
                "sold_date": "2026-07-02",
            },
            {
                "title": "Invalid Item",
                "sold_price": 0,
            },
        ]
    )

    assert len(parsed) == 1
    assert parsed[0].title == "Louis Vuitton Wallet"
    assert parsed[0].sold_price == 120000
    assert parsed[0].url == "https://example.invalid/lv-wallet"
    assert parsed[0].sold_date == "2026-07-02"


def test_parse_sold_items_rejects_invalid_payload() -> None:
    with pytest.raises(YahooAuctionLiveUnavailableError, match="missing required"):
        parse_sold_items([{"title": "Broken Item"}])


def test_calculate_average_price_and_market_data() -> None:
    parsed = parse_sold_items(
        [
            {"title": "Chanel Wallet A", "sold_price": 100000},
            {"title": "Chanel Wallet B", "sold_price": 140000},
        ]
    )

    assert calculate_average_price(parsed) == 120000.0

    market_data = to_market_price_data(parsed, product_keyword="Chanel Wallet")
    assert market_data["average_price_jpy"] == 120000.0
    assert market_data["median_price_jpy"] == 120000.0
    assert market_data["sample_count"] == 2
    assert market_data["confidence_score"] == 0.3
