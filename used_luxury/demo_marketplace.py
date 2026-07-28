"""
Demo marketplace for used luxury items.
"""

import logging
import re
import unicodedata

from config.constants import MARKETPLACE_USED_DEMO
from marketplace.base_marketplace import BaseMarketplace
from marketplace.listing_matcher import ListingMatcher
from marketplace.listing_validator import validate_listings
from models.marketplace_search_result import (
    SEARCH_ERROR,
    SEARCH_NO_LISTINGS,
    SEARCH_NO_VALID_LISTINGS,
    SEARCH_SUCCESS,
    MarketplaceSearchResult,
)
from models.product import Product
from price_compare.price_comparator import PriceComparator, PriceSelectionStrategy
from used_luxury.demo_provider import FakeUsedLuxuryProvider, UsedLuxuryProviderProtocol, UsedLuxuryResponseParser
from used_luxury.exceptions import UsedLuxuryParseError

logger = logging.getLogger(__name__)


class UsedLuxuryDemoMarketplace(BaseMarketplace):
    """Demo marketplace for used luxury brand items (fixture-based)."""

    def __init__(
        self,
        provider: UsedLuxuryProviderProtocol | None = None,
        parser: UsedLuxuryResponseParser | None = None,
        matcher: ListingMatcher | None = None,
        selection_strategy: PriceSelectionStrategy = PriceSelectionStrategy.HIGHEST,
    ) -> None:
        self._provider = provider
        self._parser = parser or UsedLuxuryResponseParser()
        self._matcher = matcher or ListingMatcher()
        self._comparator = PriceComparator()
        self.selection_strategy = selection_strategy

    @property
    def marketplace_name(self) -> str:
        return MARKETPLACE_USED_DEMO

    def search(self, product: Product, query: str | None = None) -> MarketplaceSearchResult:
        search_query = _build_search_query(product, query)
        result = MarketplaceSearchResult(
            product=product,
            query=search_query,
            marketplace_name=self.marketplace_name,
            selection_strategy=self.selection_strategy.value,
        )

        if self._provider is None:
            message = "Used luxury demo provider is not configured; skipping search."
            logger.warning(message)
            result.status = SEARCH_ERROR
            result.error_message = message
            return result

        try:
            payload = self._provider.search_items(query=search_query)
            self._parser.validate_payload(payload)
        except UsedLuxuryParseError as exc:
            result.status = SEARCH_ERROR
            result.error_message = str(exc)
            return result
        except Exception as exc:
            logger.warning("Used luxury search failed: %s", exc.__class__.__name__)
            result.status = SEARCH_ERROR
            result.error_message = "Used luxury search failed"
            return result

        meta = self._parser.parse_metadata(payload)
        result.total_results = meta.get("total_results")
        result.next_page_token = meta.get("next_page")
        result.metadata = meta

        parsed = self._parser.parse(payload, source_query=search_query)
        valid, rejected = validate_listings(parsed)
        ranked = self._matcher.match_and_rank(product, valid, exclude_invalid=True)

        result.listings = parsed
        result.valid_listings = ranked
        result.rejected_listings = rejected

        if not parsed:
            result.status = SEARCH_NO_LISTINGS
            return result
        if not ranked:
            result.status = SEARCH_NO_VALID_LISTINGS
            return result

        selected = self._comparator.select_from_listings(ranked, strategy=self.selection_strategy)
        if selected is not None:
            listing, price = selected
            result.selected_listing = listing
            result.selected_price_jpy = price
            result.status = SEARCH_SUCCESS
        else:
            result.status = SEARCH_NO_VALID_LISTINGS

        return result

    def parse_listings(self, data: object, source_query: str = "") -> list:
        if isinstance(data, dict):
            return self._parser.parse(data, source_query=source_query)
        return []


def _build_search_query(product: Product, query: str | None) -> str:
    if query and query.strip():
        return _normalize_query(query)
    if product.brand.strip() and product.model.strip():
        return _normalize_query(f"{product.brand} {product.model}")
    if product.brand.strip() and product.name.strip():
        return _normalize_query(f"{product.brand} {product.name}")
    return _normalize_query(product.name)


def _normalize_query(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value.strip())
    return re.sub(r"\s+", " ", normalized)


def create_used_luxury_demo_marketplace(
    provider: UsedLuxuryProviderProtocol | None = None,
) -> UsedLuxuryDemoMarketplace:
    """Create a demo used luxury marketplace."""
    return UsedLuxuryDemoMarketplace(provider=provider)
