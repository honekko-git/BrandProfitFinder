"""Tests for live connector fallback to fixture data."""

from __future__ import annotations

from marketplace.connectors import (
    FixtureMarketConnector,
    MarketConnectorConfig,
    MarketConnectorResolver,
    MarketConnectorSourceMode,
)
from marketplace.connectors.base import MarketConnectorUnavailableError
from marketplace.connectors.live.base import FallbackMarketConnector
from marketplace.connectors.models import MarketListing


class _FailingLiveConnector:
    def __init__(self, market_name: str) -> None:
        self._market_name = market_name

    @property
    def market_name(self) -> str:
        return self._market_name

    @property
    def source_type(self) -> str:
        return "LIVE"

    def search_products(self, query: str) -> list[MarketListing]:
        raise MarketConnectorUnavailableError("live unavailable")

    def get_product(self, url: str) -> MarketListing | None:
        raise MarketConnectorUnavailableError("live unavailable")


def test_fallback_market_connector_uses_fixture_on_live_failure() -> None:
    wrapped = FallbackMarketConnector(
        market_name="Fashionphile",
        primary=_FailingLiveConnector("Fashionphile"),
        fallback=FixtureMarketConnector("Fashionphile"),
        requested_source="LIVE",
    )

    listings = wrapped.search_products("Gucci")

    assert listings
    assert wrapped.execution.requested_source == "LIVE"
    assert wrapped.execution.actual_source == "FIXTURE"
    assert wrapped.execution.fallback_used is True


def test_market_connector_resolver_records_fixture_fallback_for_live_mode(monkeypatch) -> None:
    config = MarketConnectorConfig(enable_live=True, use_fixture=True)
    resolver = MarketConnectorResolver(config=config)
    monkeypatch.setattr(
        "marketplace.connectors.resolver._build_live_connector",
        lambda market_name, _config: _FailingLiveConnector(market_name),
    )

    resolution = resolver.resolve("Fashionphile")
    listings = resolution.connector.search_products("Gucci") if resolution.connector else []

    assert resolution.mode is MarketConnectorSourceMode.FIXTURE
    assert listings
    assert resolution.execution is not None
    assert resolution.execution.requested_source == "LIVE"
    assert resolution.execution.actual_source == "FIXTURE"
    assert resolution.execution.fallback_used is True
