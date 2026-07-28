"""
Base marketplace interface for domestic price search.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

from models.marketplace_listing import MarketplaceListing
from models.marketplace_search_result import MarketplaceSearchResult
from models.product import Product

logger = logging.getLogger(__name__)


class BaseMarketplace(ABC):
    """Abstract base class for domestic marketplace integrations."""

    @property
    @abstractmethod
    def marketplace_name(self) -> str:
        """Return normalized marketplace identifier."""

    @abstractmethod
    def search(self, product: Product, query: str | None = None) -> MarketplaceSearchResult:
        """
        Search domestic listings for the given product.

        Args:
            product: Overseas product to match.
            query: Optional override query.

        Returns:
            MarketplaceSearchResult with candidate listings.
        """

    @abstractmethod
    def parse_listings(self, data: Any) -> list[MarketplaceListing]:
        """
        Parse raw local data into marketplace listings.

        Args:
            data: Raw listing payload such as HTML or structured records.

        Returns:
            Parsed listing candidates.
        """
