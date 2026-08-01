"""Tests for Yahoo Auction live connector with injected transport."""

from __future__ import annotations

from marketplace.domestic_market import DomesticMarketRuntimeConfig, TransportMode
from marketplace.domestic_market.yahoo_auction import (
    FakeYahooAuctionTransport,
    YahooAuctionLiveDomesticMarketClient,
    calculate_average_price,
    parse_sold_items,
)


def _sample_transport() -> FakeYahooAuctionTransport:
    return FakeYahooAuctionTransport(
        default_items=[
            {
                "title": "Chanel Classic Wallet Black",
                "sold_price": 150000,
                "url": "https://example.invalid/chanel-1",
                "sold_date": "2026-07-01",
            },
            {
                "title": "Chanel Classic Wallet Beige",
                "sold_price": 170000,
                "url": "https://example.invalid/chanel-2",
                "sold_date": "2026-07-02",
            },
        ]
    )


def test_yahoo_live_connector_uses_injected_transport() -> None:
    transport = _sample_transport()
    client = YahooAuctionLiveDomesticMarketClient(
        config=DomesticMarketRuntimeConfig(
            use_fixture=False,
            enable_live=True,
            api_key="test-key",
            transport_mode=TransportMode.LIVE,
        ),
        transport=transport,
    )

    response = client.search_sold_prices("Chanel Wallet")

    assert response.query == "Chanel Wallet"
    assert response.items == (150000, 170000)
    assert response.sold_count == 2
    assert response.source == "yahoo_auction_live"


def test_yahoo_live_connector_converts_sold_prices_for_aggregator() -> None:
    client = YahooAuctionLiveDomesticMarketClient(transport=_sample_transport())

    prices = client.search_sold_items("Chanel Wallet", max_results=2)

    assert prices == [150000, 170000]


def test_yahoo_live_connector_calculates_average_price_from_transport_payload() -> None:
    transport = _sample_transport()
    raw_items = transport.search_sold_items("Chanel Wallet")
    parsed = parse_sold_items(raw_items)

    client = YahooAuctionLiveDomesticMarketClient(transport=transport)
    response = client.search_sold_prices("Chanel Wallet")

    assert response.average_price == calculate_average_price(parsed)
    assert response.average_price == 160000.0
