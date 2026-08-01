"""Tests for domestic market client resolution."""

from __future__ import annotations

from marketplace.domestic_market import (
    DomesticMarketClientResolver,
    DomesticMarketRuntimeConfig,
    DomesticMarketSourceMode,
    YahooAuctionDomesticMarketClient,
    YahooAuctionLiveDomesticMarketClient,
)
from marketplace.yahoo_auction.client import FakeYahooAuctionClient


def test_domestic_market_resolver_defaults_to_fixture() -> None:
    resolution = DomesticMarketClientResolver().resolve_yahoo_auction()

    assert resolution.client is not None
    assert resolution.mode is DomesticMarketSourceMode.FIXTURE
    assert resolution.client.market_name == "yahoo_auction"


def test_domestic_market_resolver_uses_injected_client() -> None:
    injected = YahooAuctionDomesticMarketClient(FakeYahooAuctionClient())

    resolution = DomesticMarketClientResolver().resolve_yahoo_auction(
        injected_client=injected,
    )

    assert resolution.client is injected
    assert resolution.mode is DomesticMarketSourceMode.INJECTED


def test_domestic_market_resolver_prefers_live_when_available(monkeypatch) -> None:
    config = DomesticMarketRuntimeConfig.live_only(api_key="test-key")

    def _available_search(
        self: YahooAuctionLiveDomesticMarketClient,
        query: str,
        *,
        page: int = 1,
        max_results: int = 20,
    ):
        return YahooAuctionLiveDomesticMarketClient.build_placeholder_response(
            query,
            items=(150000, 160000),
        )

    monkeypatch.setattr(YahooAuctionLiveDomesticMarketClient, "search_sold_prices", _available_search)

    resolution = DomesticMarketClientResolver(config=config).resolve_yahoo_auction()

    assert resolution.client is not None
    assert resolution.mode is DomesticMarketSourceMode.LIVE
    assert resolution.client.market_name == "yahoo_auction_live"


def test_domestic_market_resolver_falls_back_when_live_unavailable() -> None:
    config = DomesticMarketRuntimeConfig(
        use_fixture=True,
        enable_live=True,
        api_key="test-key",
    )

    resolution = DomesticMarketClientResolver(config=config).resolve_yahoo_auction()

    assert resolution.client is not None
    assert resolution.mode is DomesticMarketSourceMode.FIXTURE
