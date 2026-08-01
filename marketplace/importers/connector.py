"""Imported listings connector for resolver injection."""

from __future__ import annotations

from marketplace.connectors.models import MarketListing


class ImportedMarketConnector:
    """Serve imported MarketListing rows through the MarketConnector interface."""

    def __init__(self, *, market_name: str, listings: list[MarketListing]) -> None:
        self._market_name = market_name.strip()
        self._listings = list(listings)

    @property
    def market_name(self) -> str:
        return self._market_name

    @property
    def source_type(self) -> str:
        return "IMPORT"

    def search_products(self, query: str) -> list[MarketListing]:
        normalized_query = query.strip().lower()
        if not normalized_query:
            return list(self._listings)
        return [
            listing
            for listing in self._listings
            if normalized_query in listing.title.lower()
            or normalized_query in listing.brand.lower()
            or normalized_query in listing.category.lower()
        ]

    def get_product(self, url: str) -> MarketListing | None:
        normalized = url.strip()
        for listing in self._listings:
            if listing.url == normalized or listing.id == normalized:
                return listing
        return None
