"""
Local marketplace implementation for tests and main.py.
"""

import logging
from copy import deepcopy
from decimal import Decimal
from typing import Any

from config.constants import MARKETPLACE_LOCAL
from marketplace.base_marketplace import BaseMarketplace
from marketplace.listing_matcher import ListingMatcher
from marketplace.listing_validator import validate_listings
from models.marketplace_listing import MarketplaceListing
from models.marketplace_search_result import (
    SEARCH_NO_LISTINGS,
    SEARCH_NO_VALID_LISTINGS,
    SEARCH_SUCCESS,
    MarketplaceSearchResult,
)
from models.product import Product
from price_compare.price_comparator import PriceComparator, PriceSelectionStrategy

logger = logging.getLogger(__name__)


class LocalMarketplace(BaseMarketplace):
    """Local-only marketplace that returns injected listing candidates."""

    def __init__(
        self,
        listings_by_product_key: dict[str, list[MarketplaceListing]] | None = None,
        selection_strategy: PriceSelectionStrategy = PriceSelectionStrategy.HIGHEST,
    ) -> None:
        """
        Initialize local marketplace with injected listing data.

        Args:
            listings_by_product_key: Mapping from product SKU/name to listings.
            selection_strategy: Strategy for selecting domestic sale price.
        """
        self._listings_by_product_key = listings_by_product_key or {}
        self.selection_strategy = selection_strategy
        self._matcher = ListingMatcher()
        self._comparator = PriceComparator()

    @property
    def marketplace_name(self) -> str:
        return MARKETPLACE_LOCAL

    def search(self, product: Product, query: str | None = None) -> MarketplaceSearchResult:
        """
        Return local listings for a product without network access.

        Args:
            product: Overseas product.
            query: Optional search query override.

        Returns:
            MarketplaceSearchResult with validated and ranked listings.
        """
        search_query = query or product.name
        raw_listings = self._get_listings_for_product(product)
        parsed = self.parse_listings(raw_listings)
        valid, rejected = validate_listings(parsed)
        ranked = self._matcher.match_and_rank(product, valid, exclude_invalid=True)

        result = MarketplaceSearchResult(
            product=product,
            query=search_query,
            marketplace_name=self.marketplace_name,
            listings=parsed,
            valid_listings=ranked,
            rejected_listings=rejected,
            selection_strategy=self.selection_strategy.value,
        )

        if not parsed:
            result.status = SEARCH_NO_LISTINGS
            result.error_message = "no listings found"
            return result

        if not ranked:
            result.status = SEARCH_NO_VALID_LISTINGS
            result.error_message = "no valid listings found"
            return result

        selected = self._comparator.select_from_listings(ranked, strategy=self.selection_strategy)
        if selected is not None:
            listing, price = selected
            result.selected_listing = listing
            result.selected_price_jpy = price
            result.status = SEARCH_SUCCESS
        else:
            result.status = SEARCH_NO_VALID_LISTINGS
            result.error_message = "no selectable price found"

        logger.debug(
            "LocalMarketplace search for %r returned %d valid of %d listings",
            product.name,
            len(ranked),
            len(parsed),
        )
        return result

    def parse_listings(self, data: Any) -> list[MarketplaceListing]:
        """
        Parse injected listing records.

        Args:
            data: Iterable of MarketplaceListing instances.

        Returns:
            Copied listing list.
        """
        if not isinstance(data, list):
            return []
        return deepcopy(data)

    def _get_listings_for_product(self, product: Product) -> list[MarketplaceListing]:
        if product.sku and product.sku in self._listings_by_product_key:
            return self._listings_by_product_key[product.sku]
        if product.name in self._listings_by_product_key:
            return self._listings_by_product_key[product.name]
        return []
