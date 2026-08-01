"""Base helpers for live market connectors."""

from __future__ import annotations

from marketplace.connectors.base import MarketConnector
from marketplace.connectors.config import MarketConnectorConfig
from marketplace.connectors.execution import MarketConnectorExecutionResult
from marketplace.connectors.live.http_client import MarketHttpClient


class LiveConnectorBase:
    """Shared live connector dependencies."""

    def __init__(
        self,
        *,
        config: MarketConnectorConfig | None = None,
        http_client: MarketHttpClient | None = None,
    ) -> None:
        self._config = config or MarketConnectorConfig.from_env()
        self._http = http_client or MarketHttpClient(
            timeout_seconds=self._config.timeout_seconds,
            retry_count=self._config.retry_count,
        )


class FallbackMarketConnector:
    """Try a live connector first, then fall back to fixture data."""

    def __init__(
        self,
        *,
        market_name: str,
        primary: MarketConnector,
        fallback: MarketConnector,
        requested_source: str,
    ) -> None:
        self._market_name = market_name
        self._primary = primary
        self._fallback = fallback
        self.execution = MarketConnectorExecutionResult(
            requested_source=requested_source,
            actual_source=primary.source_type,
            fallback_used=False,
            market_name=market_name,
        )

    @property
    def market_name(self) -> str:
        return self._market_name

    @property
    def source_type(self) -> str:
        return self.execution.actual_source

    def search_products(self, query: str) -> list:
        try:
            results = self._primary.search_products(query)
            if results:
                self.execution = MarketConnectorExecutionResult(
                    requested_source=self.execution.requested_source,
                    actual_source=self._primary.source_type,
                    fallback_used=False,
                    market_name=self._market_name,
                )
                return results
        except Exception:
            pass
        results = self._fallback.search_products(query)
        self.execution = MarketConnectorExecutionResult(
            requested_source=self.execution.requested_source,
            actual_source=self._fallback.source_type,
            fallback_used=True,
            market_name=self._market_name,
        )
        return results

    def get_product(self, url: str):
        try:
            listing = self._primary.get_product(url)
            if listing is not None:
                self.execution = MarketConnectorExecutionResult(
                    requested_source=self.execution.requested_source,
                    actual_source=self._primary.source_type,
                    fallback_used=False,
                    market_name=self._market_name,
                )
                return listing
        except Exception:
            pass
        listing = self._fallback.get_product(url)
        if listing is not None:
            self.execution = MarketConnectorExecutionResult(
                requested_source=self.execution.requested_source,
                actual_source=self._fallback.source_type,
                fallback_used=True,
                market_name=self._market_name,
            )
        return listing
