"""Tests for Yahoo Auction live domestic market client foundation."""

from __future__ import annotations

import pytest

from marketplace.domestic_market.config import DomesticMarketRuntimeConfig
from marketplace.domestic_market.yahoo_auction import (
    YahooAuctionLiveDomesticMarketClient,
    YahooAuctionLiveResponse,
    YahooAuctionLiveUnavailableError,
)


def test_yahoo_live_response_model_fields() -> None:
    response = YahooAuctionLiveResponse(
        query="Chanel Wallet",
        items=(150000, 160000, 155000),
        average_price=155000.0,
        sold_count=3,
        source="yahoo_auction_live",
        retrieved_at="2026-07-30T00:00:00+00:00",
    )

    assert response.query == "Chanel Wallet"
    assert response.items == (150000, 160000, 155000)
    assert response.average_price == 155000.0
    assert response.sold_count == 3
    assert response.source == "yahoo_auction_live"
    assert response.retrieved_at == "2026-07-30T00:00:00+00:00"


def test_yahoo_live_client_builds_placeholder_response() -> None:
    response = YahooAuctionLiveDomesticMarketClient.build_placeholder_response(
        "Louis Vuitton Wallet",
        items=(120000, 130000),
    )

    assert response.query == "Louis Vuitton Wallet"
    assert response.items == (120000, 130000)
    assert response.average_price == 125000.0
    assert response.sold_count == 2


def test_yahoo_live_client_disabled_raises_unavailable() -> None:
    client = YahooAuctionLiveDomesticMarketClient(
        config=DomesticMarketRuntimeConfig.default(),
    )

    with pytest.raises(YahooAuctionLiveUnavailableError, match="not configured"):
        client.search_sold_prices("Chanel Wallet")


def test_yahoo_live_client_unavailable_transport_raises() -> None:
    client = YahooAuctionLiveDomesticMarketClient(
        config=DomesticMarketRuntimeConfig.live_only(api_key="test-key"),
    )

    with pytest.raises(YahooAuctionLiveUnavailableError, match="not configured"):
        client.search_sold_prices("Chanel Wallet")
