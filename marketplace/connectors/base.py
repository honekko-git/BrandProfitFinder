"""Market connector protocol and shared exceptions."""

from __future__ import annotations

from typing import Protocol

from marketplace.connectors.models import MarketListing


class MarketConnectorUnavailableError(RuntimeError):
    """Raised when a live market connector is not available."""


class MarketConnector(Protocol):
    """Protocol for interchangeable market data connectors."""

    @property
    def market_name(self) -> str:
        """Return the display market name."""

    @property
    def source_type(self) -> str:
        """Return FIXTURE, LIVE, or INJECTED."""

    def search_products(self, query: str) -> list[MarketListing]:
        """Search market listings for one query string."""

    def get_product(self, url: str) -> MarketListing | None:
        """Return one listing by URL when available."""
