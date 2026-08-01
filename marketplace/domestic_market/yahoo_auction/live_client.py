"""Yahoo Auction live domestic market client."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from marketplace.domestic_market.yahoo_auction.exceptions import YahooAuctionLiveUnavailableError
from marketplace.domestic_market.yahoo_auction.models import YahooAuctionLiveResponse
from marketplace.domestic_market.yahoo_auction.parser import parse_sold_items, calculate_average_price
from marketplace.domestic_market.yahoo_auction.transport import YahooAuctionTransport

if TYPE_CHECKING:
    from marketplace.domestic_market.config import DomesticMarketRuntimeConfig


class YahooAuctionLiveDomesticMarketClient:
    """Live Yahoo Auction sold-price entry point with injectable transport."""

    def __init__(
        self,
        *,
        config: DomesticMarketRuntimeConfig | None = None,
        transport: YahooAuctionTransport | None = None,
    ) -> None:
        if config is None:
            from marketplace.domestic_market.config import DomesticMarketRuntimeConfig

            config = DomesticMarketRuntimeConfig.default()
        self._config = config
        self._transport = transport

    @property
    def market_name(self) -> str:
        return "yahoo_auction_live"

    @property
    def config(self) -> DomesticMarketRuntimeConfig:
        return self._config

    @property
    def transport(self) -> YahooAuctionTransport | None:
        return self._transport

    def search_sold_prices(
        self,
        query: str,
        *,
        page: int = 1,
        max_results: int = 20,
    ) -> YahooAuctionLiveResponse:
        """Search sold Yahoo Auction prices through the live transport layer."""
        normalized_query = query.strip()
        if not normalized_query:
            raise YahooAuctionLiveUnavailableError("Yahoo Auction live query must not be blank")

        if self._transport is None:
            if not self._config.is_live_configured():
                raise YahooAuctionLiveUnavailableError("Yahoo Auction live search is not configured")
            raise YahooAuctionLiveUnavailableError("Yahoo Auction live transport is not configured")

        _ = page
        raw_items = self._transport.search_sold_items(normalized_query)
        parsed_items = parse_sold_items(raw_items)
        if max_results > 0:
            parsed_items = parsed_items[:max_results]
        if not parsed_items:
            raise YahooAuctionLiveUnavailableError("Yahoo Auction live search returned no sold listings")

        prices = tuple(item.sold_price for item in parsed_items)
        return YahooAuctionLiveResponse(
            query=normalized_query,
            items=prices,
            average_price=calculate_average_price(parsed_items),
            sold_count=len(parsed_items),
            source="yahoo_auction_live",
            retrieved_at=datetime.now(UTC).isoformat(),
        )

    def search_sold_items(
        self,
        query: str,
        *,
        page: int = 1,
        max_results: int = 20,
    ) -> list[int]:
        """Return sold listing prices for domestic market aggregation."""
        response = self.search_sold_prices(query, page=page, max_results=max_results)
        return list(response.items)

    @staticmethod
    def build_placeholder_response(query: str, *, items: tuple[int, ...]) -> YahooAuctionLiveResponse:
        """Build one normalized live response for tests and future transport wiring."""
        average_price = sum(items) / len(items) if items else 0.0
        return YahooAuctionLiveResponse(
            query=query.strip(),
            items=items,
            average_price=average_price,
            sold_count=len(items),
            source="yahoo_auction_live",
            retrieved_at=datetime.now(UTC).isoformat(),
        )
