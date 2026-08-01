"""Pipeline tests for market source truth from CLI through showcase."""

from __future__ import annotations

import io

import httpx

from marketplace.domestic_market import (
    DomesticMarketRuntimeConfig,
    FakeYahooAuctionTransport,
    MarketExecutionResult,
    TransportMode,
)
from marketplace.domestic_market.yahoo_auction import YahooAuctionHTTPTransport
from profit_discovery.cli.discovery_command import (
    DiscoveryCommandOptions,
    build_default_discovery_runner,
    build_domestic_market_runtime_config,
    read_runtime_market_execution,
    run_discovery_command,
)
from profit_discovery.showcase.formatter import ShowcaseFormatter


def test_market_runtime_truth_pipeline_live_success() -> None:
    transport = FakeYahooAuctionTransport(
        default_items=[
            {"title": "Chanel Classic Wallet Black Caviar", "sold_price": 155000},
            {"title": "Chanel CC Wallet Medium", "sold_price": 160000},
        ]
    )
    runner = build_default_discovery_runner(
        market_config=build_domestic_market_runtime_config(live_market=True),
        injected_transport=transport,
    )

    result = run_discovery_command(
        DiscoveryCommandOptions(
            brands=["CHANEL"],
            keyword="wallet",
            max_results_per_brand=1,
            live_market=True,
        ),
        runner=runner,
        injected_transport=transport,
        output=io.StringIO(),
    )
    execution = read_runtime_market_execution(runner)
    showcase_items = ShowcaseFormatter().to_showcase_opportunities(
        result.ranked_demand_opportunities,
        market_execution=execution,
    )

    assert execution == MarketExecutionResult(
        requested_mode="LIVE",
        actual_source="Yahoo Auction LIVE",
        fallback_used=False,
        client_name="FakeYahooAuctionTransport",
    )
    assert showcase_items
    assert showcase_items[0].requested_market_mode == "LIVE"
    assert showcase_items[0].actual_market_source == "Yahoo Auction LIVE"
    assert showcase_items[0].fallback_used is False


def test_market_runtime_truth_pipeline_http_fallback() -> None:
    def failing_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "server down"})

    config = DomesticMarketRuntimeConfig(
        use_fixture=True,
        enable_live=True,
        api_key="test-api-key",
        transport_mode=TransportMode.LIVE,
        endpoint="https://example.invalid/yahoo-auction/sold",
        retry_count=1,
    )
    transport = YahooAuctionHTTPTransport(
        config=config,
        client=httpx.Client(transport=httpx.MockTransport(failing_handler)),
    )
    runner = build_default_discovery_runner(
        market_config=build_domestic_market_runtime_config(live_market=True),
        injected_transport=transport,
    )

    result = run_discovery_command(
        DiscoveryCommandOptions(
            brands=["CHANEL"],
            keyword="wallet",
            max_results_per_brand=1,
            live_market=True,
        ),
        runner=runner,
        injected_transport=transport,
        output=io.StringIO(),
    )
    execution = read_runtime_market_execution(runner)
    showcase_items = ShowcaseFormatter().to_showcase_opportunities(
        result.ranked_demand_opportunities,
        market_execution=execution,
    )

    assert execution.requested_mode == "LIVE"
    assert execution.actual_source == "Fixture"
    assert execution.fallback_used is True
    assert showcase_items
    assert showcase_items[0].actual_market_source == "Fixture"
    assert showcase_items[0].fallback_used is True
