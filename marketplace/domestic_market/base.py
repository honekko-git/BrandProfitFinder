"""Domestic market client protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class DomesticMarketClient(Protocol):
    """Contract for domestic sold-price market clients."""

    @property
    def market_name(self) -> str:
        """Return normalized domestic market identifier."""

    def search_sold_items(
        self,
        query: str,
        *,
        page: int = 1,
        max_results: int = 20,
    ) -> list[int]:
        """
        Search sold listings and return JPY prices.

        Args:
            query: Product search query.
            page: 1-based page number.
            max_results: Maximum number of prices to return.
        """
