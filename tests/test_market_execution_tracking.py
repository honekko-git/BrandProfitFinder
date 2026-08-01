"""Tests for market execution truth tracking."""

from __future__ import annotations

import httpx

from marketplace.domestic_market import (
    DomesticMarketClientResolver,
    DomesticMarketRuntimeConfig,
    FakeYahooAuctionTransport,
    MarketExecutionResult,
    TransportMode,
    read_market_execution,
)
from marketplace.domestic_market.yahoo_auction import YahooAuctionHTTPTransport


def _fixture_prices() -> list[int]:
    return [155000, 160000, 165000, 158000, 162000]


def test_market_execution_live_success_records_actual_source() -> None:
    transport = FakeYahooAuctionTransport(
        default_items=[
            {"title": "Chanel Classic Wallet", "sold_price": 155000},
            {"title": "Chanel CC Wallet Medium", "sold_price": 160000},
        ]
    )
    resolution = DomesticMarketClientResolver(
        config=DomesticMarketRuntimeConfig(
            use_fixture=True,
            enable_live=True,
            api_key="test-api-key",
            transport_mode=TransportMode.LIVE,
        ),
    ).resolve_yahoo_auction(injected_transport=transport)
    assert resolution.client is not None

    prices = resolution.client.search_sold_items("Chanel wallet", max_results=20)
    execution = read_market_execution(resolution.client)

    assert prices == [155000, 160000]
    assert execution == MarketExecutionResult(
        requested_mode="LIVE",
        actual_source="Yahoo Auction LIVE",
        fallback_used=False,
        client_name="FakeYahooAuctionTransport",
    )


def test_market_execution_fixture_mode_records_fixture_source() -> None:
    resolution = DomesticMarketClientResolver().resolve_yahoo_auction()
    assert resolution.client is not None

    prices = resolution.client.search_sold_items("Chanel wallet", max_results=20)
    execution = read_market_execution(resolution.client)

    assert prices == _fixture_prices()
    assert execution is not None
    assert execution.requested_mode == "FIXTURE"
    assert execution.actual_source == "Fixture"
    assert execution.fallback_used is False


def test_market_execution_http_fallback_records_fixture_metadata() -> None:
    def failing_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "server down"})

    failing_transport = YahooAuctionHTTPTransport(
        config=DomesticMarketRuntimeConfig(
            use_fixture=True,
            enable_live=True,
            api_key="test-api-key",
            transport_mode=TransportMode.LIVE,
            endpoint="https://example.invalid/yahoo-auction/sold",
            retry_count=1,
        ),
        client=httpx.Client(transport=httpx.MockTransport(failing_handler)),
    )
    resolution = DomesticMarketClientResolver(
        config=DomesticMarketRuntimeConfig(
            use_fixture=True,
            enable_live=True,
            api_key="test-api-key",
            transport_mode=TransportMode.LIVE,
            endpoint="https://example.invalid/yahoo-auction/sold",
            retry_count=1,
        ),
    ).resolve_yahoo_auction(injected_transport=failing_transport)
    assert resolution.client is not None

    prices = resolution.client.search_sold_items("Chanel wallet", max_results=20)
    execution = read_market_execution(resolution.client)

    assert prices == _fixture_prices()
    assert execution == MarketExecutionResult(
        requested_mode="LIVE",
        actual_source="Fixture",
        fallback_used=True,
        client_name="YahooAuctionDomesticMarketClient",
    )


def test_market_execution_resolution_includes_metadata() -> None:
    resolution = DomesticMarketClientResolver().resolve_yahoo_auction()

    assert resolution.execution == MarketExecutionResult(
        requested_mode="FIXTURE",
        actual_source="Fixture",
        fallback_used=False,
        client_name="YahooAuctionDomesticMarketClient",
    )
