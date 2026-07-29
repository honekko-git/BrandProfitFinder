"""Yahoo Auction domestic market client protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from marketplace.yahoo_auction.models import YahooAuctionListing


@runtime_checkable
class YahooAuctionClientProtocol(Protocol):
    """Fixture/API contract for domestic sold Yahoo Auction listings."""

    def search_sold_items(
        self,
        keyword: str,
        *,
        page: int = 1,
        max_results: int = 20,
    ) -> list[YahooAuctionListing]:
        """
        Search sold Yahoo Auction listings for domestic market intelligence.

        Args:
            keyword: Product search keyword.
            page: 1-based page number.
            max_results: Maximum number of listings to return.

        Returns:
            Sold listings in source order.
        """
