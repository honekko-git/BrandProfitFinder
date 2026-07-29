"""Placeholder Rakuma domestic market client."""

from __future__ import annotations


class RakumaDomesticMarketClient:
    """Future Rakuma integration point that currently returns no sold prices."""

    @property
    def market_name(self) -> str:
        return "rakuma"

    def search_sold_items(
        self,
        query: str,
        *,
        page: int = 1,
        max_results: int = 20,
    ) -> list[int]:
        _ = query, page, max_results
        return []
