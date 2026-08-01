"""Mercari live connector stub for future implementation."""

from __future__ import annotations

from marketplace.connectors.base import MarketConnectorUnavailableError
from marketplace.connectors.models import MarketListing


class MercariLiveConnector:
    """Placeholder Mercari connector reserved for a future live integration."""

    MARKET_NAME = "Mercari"

    @property
    def market_name(self) -> str:
        return self.MARKET_NAME

    @property
    def source_type(self) -> str:
        return "LIVE"

    def search_products(self, query: str) -> list[MarketListing]:
        raise MarketConnectorUnavailableError("Mercari live connector is not implemented yet")

    def get_product(self, url: str) -> MarketListing | None:
        raise MarketConnectorUnavailableError("Mercari live connector is not implemented yet")
