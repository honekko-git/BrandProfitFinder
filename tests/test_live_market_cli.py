"""Tests for discovery CLI live market activation."""

from __future__ import annotations

import httpx

from marketplace.domestic_market import DomesticMarketRuntimeConfig, TransportMode
from marketplace.domestic_market.yahoo_auction import YahooAuctionHTTPTransport
from profit_discovery.cli.discovery_command import (
    DiscoveryCommandOptions,
    build_default_market_aggregator,
    build_discovery_parser,
    build_domestic_market_runtime_config,
    resolve_domestic_market_client,
)


def test_discovery_cli_defaults_to_fixture_runtime_config() -> None:
    parser = build_discovery_parser()
    namespace = parser.parse_args(["--brands", "CHANEL"])
    options = DiscoveryCommandOptions.from_namespace(namespace)

    config = build_domestic_market_runtime_config(live_market=options.live_market)

    assert options.live_market is False
    assert config.use_fixture is True
    assert config.enable_live is False
    assert config.transport_mode is TransportMode.FIXTURE


def test_discovery_cli_parses_live_market_flag() -> None:
    parser = build_discovery_parser()
    namespace = parser.parse_args(["--brands", "CHANEL", "--live-market"])
    options = DiscoveryCommandOptions.from_namespace(namespace)

    assert options.live_market is True


def test_live_market_runtime_config_generation(monkeypatch) -> None:
    monkeypatch.setattr("config.settings.YAHOO_CLIENT_ID", "cli-test-key")
    monkeypatch.setattr(
        "config.settings.YAHOO_AUCTION_DATA_SOURCE",
        "https://example.invalid/yahoo-auction/sold",
    )
    monkeypatch.setattr("config.settings.YAHOO_AUCTION_TIMEOUT", 7)
    monkeypatch.setattr("config.settings.YAHOO_AUCTION_MAX_RETRIES", 2)

    config = build_domestic_market_runtime_config(live_market=True)

    assert config.use_fixture is True
    assert config.enable_live is True
    assert config.transport_mode is TransportMode.LIVE
    assert config.api_key == "cli-test-key"
    assert config.endpoint == "https://example.invalid/yahoo-auction/sold"
    assert config.timeout_seconds == 7.0
    assert config.retry_count == 2


def test_live_market_cli_resolver_falls_back_when_live_unconfigured() -> None:
    resolution = resolve_domestic_market_client(
        DomesticMarketRuntimeConfig(
            use_fixture=False,
            enable_live=True,
            api_key="test-api-key",
            transport_mode=TransportMode.LIVE,
        ),
    )
    assert resolution.client is not None
    prices = resolution.client.search_sold_items("Chanel wallet", max_results=20)

    assert resolution.execution is not None
    assert resolution.execution.actual_source == "Fixture"
    assert resolution.execution.fallback_used is True
    assert prices == [155000, 160000, 165000, 158000, 162000]


def test_live_market_cli_resolver_falls_back_on_http_error() -> None:
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
    config = DomesticMarketRuntimeConfig(
        use_fixture=True,
        enable_live=True,
        api_key="test-api-key",
        transport_mode=TransportMode.LIVE,
        endpoint="https://example.invalid/yahoo-auction/sold",
        retry_count=1,
    )

    resolution = resolve_domestic_market_client(
        config,
        injected_transport=failing_transport,
    )
    assert resolution.client is not None
    prices = resolution.client.search_sold_items("Chanel wallet", max_results=20)

    assert prices == [155000, 160000, 165000, 158000, 162000]


def test_live_market_cli_builds_aggregator_with_injected_transport() -> None:
    from marketplace.domestic_market import FakeYahooAuctionTransport

    transport = FakeYahooAuctionTransport(
        default_items=[
            {"title": "Chanel Classic Wallet", "sold_price": 155000},
        ]
    )
    config = build_domestic_market_runtime_config(live_market=True)
    aggregator, _resolution = build_default_market_aggregator(
        config,
        injected_transport=transport,
    )

    result = aggregator.aggregate("Chanel wallet", max_results=5)

    assert result.average_price_jpy == 155000.0
