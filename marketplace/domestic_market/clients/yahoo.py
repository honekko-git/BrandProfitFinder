"""Yahoo Auction adapter for domestic market aggregation."""

from __future__ import annotations

from marketplace.yahoo_auction.base import YahooAuctionClientProtocol


class YahooAuctionDomesticMarketClient:
    """Adapt Yahoo Auction sold listing search to DomesticMarketClient."""

    def __init__(self, client: YahooAuctionClientProtocol) -> None:
        self._client = client

    @property
    def market_name(self) -> str:
        return "yahoo_auction"

    def search_sold_items(
        self,
        query: str,
        *,
        page: int = 1,
        max_results: int = 20,
    ) -> list[int]:
        listings = self._client.search_sold_items(
            query,
            page=page,
            max_results=max_results,
        )
        return [listing.price_jpy for listing in listings]
