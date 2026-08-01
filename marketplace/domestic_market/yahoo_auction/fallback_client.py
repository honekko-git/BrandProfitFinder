"""Yahoo Auction domestic market client with live-to-fixture fallback."""

from __future__ import annotations

from marketplace.domestic_market.base import DomesticMarketClient
from marketplace.domestic_market.execution import MarketExecutionResult, resolve_client_name
from marketplace.domestic_market.yahoo_auction.exceptions import (
    YahooAuctionLiveUnavailableError,
    YahooAuctionTransportError,
)


class YahooAuctionFallbackDomesticMarketClient:
    """Try a live Yahoo Auction client and fall back to fixture prices on failure."""

    def __init__(
        self,
        *,
        primary: DomesticMarketClient,
        fallback: DomesticMarketClient,
        requested_mode: str = "LIVE",
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._requested_mode = requested_mode
        self._execution: MarketExecutionResult | None = None

    @property
    def market_name(self) -> str:
        return self._primary.market_name

    @property
    def execution(self) -> MarketExecutionResult | None:
        return self._execution

    def search_sold_items(
        self,
        query: str,
        *,
        page: int = 1,
        max_results: int = 20,
    ) -> list[int]:
        """Return sold prices from live transport, falling back to fixture data."""
        try:
            prices = self._primary.search_sold_items(
                query,
                page=page,
                max_results=max_results,
            )
            if prices:
                self._execution = MarketExecutionResult(
                    requested_mode=self._requested_mode,
                    actual_source="Yahoo Auction LIVE",
                    fallback_used=False,
                    client_name=resolve_client_name(self._primary),
                )
                return prices
        except (YahooAuctionLiveUnavailableError, YahooAuctionTransportError):
            pass
        prices = self._fallback.search_sold_items(
            query,
            page=page,
            max_results=max_results,
        )
        self._execution = MarketExecutionResult(
            requested_mode=self._requested_mode,
            actual_source="Fixture",
            fallback_used=True,
            client_name=resolve_client_name(self._fallback),
        )
        return prices
