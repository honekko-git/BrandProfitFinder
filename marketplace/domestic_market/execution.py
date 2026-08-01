"""Market execution truth tracking for domestic market runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from marketplace.domestic_market.base import DomesticMarketClient

if TYPE_CHECKING:
    from marketplace.domestic_market.config import DomesticMarketRuntimeConfig


@dataclass(frozen=True, slots=True)
class MarketExecutionResult:
    """Tracks requested market mode versus actual runtime data source."""

    requested_mode: str
    actual_source: str
    fallback_used: bool
    client_name: str


def requested_mode_from_config(config: DomesticMarketRuntimeConfig) -> str:
    """Return the requested market mode label from runtime config."""
    return "LIVE" if config.prefers_live() else "FIXTURE"


def resolve_client_name(client: object) -> str:
    """Return a stable client or transport name for execution metadata."""
    if client.__class__.__name__ == "YahooAuctionLiveDomesticMarketClient":
        transport = getattr(client, "transport", None)
        if transport is not None:
            return type(transport).__name__
        return "YahooAuctionLiveDomesticMarketClient"
    return type(client).__name__


def resolve_actual_source(*, client: DomesticMarketClient, live: bool) -> str:
    """Return the human-readable actual source label for one client."""
    if live:
        return "Yahoo Auction LIVE"
    return "Fixture"


def read_market_execution(client: DomesticMarketClient) -> MarketExecutionResult | None:
    """Read execution metadata from a domestic market client if available."""
    execution = getattr(client, "execution", None)
    if isinstance(execution, MarketExecutionResult):
        return execution
    return None


class ExecutionTrackingDomesticMarketClient:
    """Wrap one domestic market client and record runtime execution truth."""

    def __init__(
        self,
        client: DomesticMarketClient,
        *,
        requested_mode: str,
    ) -> None:
        self._client = client
        self._requested_mode = requested_mode
        self._execution: MarketExecutionResult | None = None

    @property
    def market_name(self) -> str:
        return self._client.market_name

    @property
    def execution(self) -> MarketExecutionResult | None:
        inner_execution = read_market_execution(self._client)
        if inner_execution is not None:
            return inner_execution
        return self._execution

    def search_sold_items(
        self,
        query: str,
        *,
        page: int = 1,
        max_results: int = 20,
    ) -> list[int]:
        prices = self._client.search_sold_items(
            query,
            page=page,
            max_results=max_results,
        )
        inner_execution = read_market_execution(self._client)
        if inner_execution is not None:
            self._execution = inner_execution
            return prices

        live = self._client.market_name.endswith("_live") or self._client.market_name == "yahoo_auction_live"
        self._execution = MarketExecutionResult(
            requested_mode=self._requested_mode,
            actual_source=resolve_actual_source(client=self._client, live=live),
            fallback_used=False,
            client_name=resolve_client_name(self._client),
        )
        return prices


def wrap_with_execution_tracking(
    client: DomesticMarketClient,
    *,
    requested_mode: str,
) -> DomesticMarketClient:
    """Wrap a client with execution tracking when it does not already track truth."""
    if isinstance(client, ExecutionTrackingDomesticMarketClient):
        return client
    if client.__class__.__name__ == "YahooAuctionFallbackDomesticMarketClient":
        return client
    return ExecutionTrackingDomesticMarketClient(client, requested_mode=requested_mode)
