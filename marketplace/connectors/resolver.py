"""Market connector resolution with injection, live, then fixture priority."""

from __future__ import annotations

from enum import StrEnum

from marketplace.connectors.base import MarketConnector, MarketConnectorUnavailableError
from marketplace.connectors.config import MarketConnectorConfig
from marketplace.connectors.execution import MarketConnectorExecutionResult
from marketplace.connectors.fixtures.fixture_connector import FixtureMarketConnector, SUPPORTED_MARKETS
from marketplace.connectors.live.base import FallbackMarketConnector
from marketplace.connectors.live.fashionphile.connector import FashionphileLiveConnector
from marketplace.connectors.live.mercari.connector import MercariLiveConnector
from marketplace.connectors.live.yahoo.connector import YahooAuctionLiveConnector


class MarketConnectorSourceMode(StrEnum):
    """Resolved market connector source mode."""

    INJECTED = "INJECTED"
    LIVE = "LIVE"
    FIXTURE = "FIXTURE"


class MarketConnectorResolution:
    """Result of resolving one market connector."""

    __slots__ = ("market_name", "connector", "mode", "execution")

    def __init__(
        self,
        *,
        market_name: str,
        connector: MarketConnector | None,
        mode: MarketConnectorSourceMode | None = None,
        execution: MarketConnectorExecutionResult | None = None,
    ) -> None:
        self.market_name = market_name
        self.connector = connector
        self.mode = mode
        self.execution = execution


class MarketConnectorResolver:
    """Resolve market connectors with injection, live, then fixture priority."""

    def __init__(self, config: MarketConnectorConfig | None = None) -> None:
        self._config = config or MarketConnectorConfig.from_env()

    @property
    def config(self) -> MarketConnectorConfig:
        return self._config

    def resolve(
        self,
        market_name: str,
        *,
        injected_connector: MarketConnector | None = None,
    ) -> MarketConnectorResolution:
        normalized = market_name.strip()
        requested_source = "LIVE" if self._config.enable_live else "FIXTURE"

        if injected_connector is not None:
            return MarketConnectorResolution(
                market_name=normalized,
                connector=injected_connector,
                mode=MarketConnectorSourceMode.INJECTED,
                execution=MarketConnectorExecutionResult(
                    requested_source=requested_source,
                    actual_source=injected_connector.source_type,
                    fallback_used=False,
                    market_name=normalized,
                ),
            )

        if self._config.enable_live and normalized in SUPPORTED_MARKETS:
            live_resolution = self._resolve_live_with_fallback(normalized, requested_source=requested_source)
            if live_resolution.connector is not None:
                return live_resolution

        if self._config.use_fixture and normalized in SUPPORTED_MARKETS:
            fixture = FixtureMarketConnector(normalized)
            return MarketConnectorResolution(
                market_name=normalized,
                connector=fixture,
                mode=MarketConnectorSourceMode.FIXTURE,
                execution=MarketConnectorExecutionResult(
                    requested_source=requested_source,
                    actual_source="FIXTURE",
                    fallback_used=self._config.enable_live,
                    market_name=normalized,
                ),
            )

        return MarketConnectorResolution(
            market_name=normalized,
            connector=None,
            mode=None,
            execution=None,
        )

    def resolve_purchase_connector(
        self,
        purchase_source: str,
        *,
        injected_connector: MarketConnector | None = None,
    ) -> MarketConnectorResolution:
        return self.resolve(purchase_source, injected_connector=injected_connector)

    def resolve_selling_connector(
        self,
        selling_market: str,
        *,
        injected_connector: MarketConnector | None = None,
    ) -> MarketConnectorResolution:
        return self.resolve(selling_market, injected_connector=injected_connector)

    def _resolve_live_with_fallback(
        self,
        market_name: str,
        *,
        requested_source: str,
    ) -> MarketConnectorResolution:
        live_connector = _build_live_connector(market_name, self._config)
        if not self._config.use_fixture:
            try:
                if live_connector.search_products(""):
                    return MarketConnectorResolution(
                        market_name=market_name,
                        connector=live_connector,
                        mode=MarketConnectorSourceMode.LIVE,
                        execution=MarketConnectorExecutionResult(
                            requested_source=requested_source,
                            actual_source="LIVE",
                            fallback_used=False,
                            market_name=market_name,
                        ),
                    )
            except Exception:
                return MarketConnectorResolution(
                    market_name=market_name,
                    connector=None,
                    mode=None,
                    execution=MarketConnectorExecutionResult(
                        requested_source=requested_source,
                        actual_source="FIXTURE",
                        fallback_used=True,
                        market_name=market_name,
                    ),
                )
            return MarketConnectorResolution(
                market_name=market_name,
                connector=None,
                mode=None,
                execution=None,
            )

        fallback = FixtureMarketConnector(market_name)
        wrapped = FallbackMarketConnector(
            market_name=market_name,
            primary=live_connector,
            fallback=fallback,
            requested_source=requested_source,
        )
        wrapped.search_products("")
        mode = (
            MarketConnectorSourceMode.FIXTURE
            if wrapped.execution.fallback_used
            else MarketConnectorSourceMode.LIVE
        )
        return MarketConnectorResolution(
            market_name=market_name,
            connector=wrapped,
            mode=mode,
            execution=wrapped.execution,
        )


def _build_live_connector(market_name: str, config: MarketConnectorConfig) -> MarketConnector:
    if market_name == "Fashionphile":
        return FashionphileLiveConnector(config=config)
    if market_name == "Yahoo Auction":
        return YahooAuctionLiveConnector(config=config)
    if market_name == "Mercari":
        return MercariLiveConnector()
    raise MarketConnectorUnavailableError(f"Unsupported live market: {market_name}")
