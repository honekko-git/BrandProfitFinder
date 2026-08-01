"""Tests for market connector resolver priority."""

from __future__ import annotations

from marketplace.connectors import (
    FixtureMarketConnector,
    MarketConnectorConfig,
    MarketConnectorResolver,
    MarketConnectorSourceMode,
)
from marketplace.connectors.base import MarketConnector
from marketplace.connectors.live.base import FallbackMarketConnector
from marketplace.connectors.models import MarketListing


class _InjectedConnector(FixtureMarketConnector):
    @property
    def source_type(self) -> str:
        return "INJECTED"


class _LiveWithData:
    def __init__(self, market_name: str) -> None:
        self._market_name = market_name

    @property
    def market_name(self) -> str:
        return self._market_name

    @property
    def source_type(self) -> str:
        return "LIVE"

    def search_products(self, query: str) -> list[MarketListing]:
        fixture = FixtureMarketConnector(self._market_name)
        return fixture.search_products(query)

    def get_product(self, url: str) -> MarketListing | None:
        return None


def test_market_connector_resolver_uses_fixture_by_default() -> None:
    resolution = MarketConnectorResolver().resolve("Fashionphile")

    assert resolution.connector is not None
    assert resolution.mode is MarketConnectorSourceMode.FIXTURE
    assert resolution.connector.market_name == "Fashionphile"
    assert resolution.execution is not None
    assert resolution.execution.actual_source == "FIXTURE"
    assert resolution.execution.fallback_used is False


def test_market_connector_resolver_prefers_injected_connector() -> None:
    injected = _InjectedConnector("Fashionphile")
    resolution = MarketConnectorResolver().resolve(
        "Fashionphile",
        injected_connector=injected,
    )

    assert resolution.connector is injected
    assert resolution.mode is MarketConnectorSourceMode.INJECTED
    assert resolution.execution is not None
    assert resolution.execution.actual_source == "INJECTED"


def test_market_connector_resolver_falls_back_to_fixture_when_live_empty() -> None:
    config = MarketConnectorConfig(enable_live=True, use_fixture=True)
    resolution = MarketConnectorResolver(config=config).resolve("Mercari")

    assert resolution.connector is not None
    assert resolution.mode is MarketConnectorSourceMode.FIXTURE
    assert isinstance(resolution.connector, FallbackMarketConnector)
    assert resolution.execution is not None
    assert resolution.execution.fallback_used is True


def test_market_connector_resolver_uses_live_when_listings_available(monkeypatch) -> None:
    config = MarketConnectorConfig(enable_live=True, use_fixture=True)
    resolver = MarketConnectorResolver(config=config)
    monkeypatch.setattr(
        "marketplace.connectors.resolver._build_live_connector",
        lambda market_name, _config: _LiveWithData(market_name),
    )

    resolution = resolver.resolve("The RealReal")

    assert resolution.connector is not None
    assert resolution.mode is MarketConnectorSourceMode.LIVE
    assert resolution.execution is not None
    assert resolution.execution.actual_source == "LIVE"
    assert resolution.execution.fallback_used is False
