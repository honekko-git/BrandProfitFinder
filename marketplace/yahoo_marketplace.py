"""
Yahoo Shopping marketplace integration.
"""

import logging
import re
import unicodedata
from typing import Any

from config.constants import MARKETPLACE_YAHOO
from marketplace.base_marketplace import BaseMarketplace
from marketplace.listing_matcher import ListingMatcher
from marketplace.listing_validator import validate_listings
from marketplace.yahoo_api_client import YahooApiClient
from marketplace.yahoo_exceptions import YahooApiError, YahooConfigError
from marketplace.yahoo_response_parser import YahooResponseParser
from marketplace.yahoo_settings import YahooApiSettings
from models.marketplace_listing import MarketplaceListing
from models.marketplace_search_result import (
    SEARCH_ERROR,
    SEARCH_NO_LISTINGS,
    SEARCH_NO_VALID_LISTINGS,
    SEARCH_SUCCESS,
    MarketplaceSearchResult,
)
from models.product import Product
from price_compare.price_comparator import PriceComparator, PriceSelectionStrategy

logger = logging.getLogger(__name__)

_JAN_PATTERN = re.compile(r"^\d{8,13}$")


class YahooMarketplace(BaseMarketplace):
    """Domestic marketplace implementation backed by Yahoo Shopping API."""

    def __init__(
        self,
        client: YahooApiClient,
        parser: YahooResponseParser | None = None,
        matcher: ListingMatcher | None = None,
        selection_strategy: PriceSelectionStrategy = PriceSelectionStrategy.HIGHEST,
    ) -> None:
        """
        Initialize Yahoo marketplace.

        Args:
            client: Yahoo API client.
            parser: Response parser.
            matcher: Listing matcher.
            selection_strategy: Domestic price selection strategy.
        """
        self._client = client
        self._parser = parser or YahooResponseParser()
        self._matcher = matcher or ListingMatcher()
        self._comparator = PriceComparator()
        self.selection_strategy = selection_strategy

    @property
    def marketplace_name(self) -> str:
        return MARKETPLACE_YAHOO

    def search(self, product: Product, query: str | None = None) -> MarketplaceSearchResult:
        """
        Search Yahoo Shopping for domestic listing candidates.

        Args:
            product: Overseas product to match.
            query: Optional query override.

        Returns:
            MarketplaceSearchResult with validated and ranked listings.
        """
        search_query, jan_code = self._build_search_terms(product, query)
        result = MarketplaceSearchResult(
            product=product,
            query=search_query or jan_code,
            marketplace_name=self.marketplace_name,
            selection_strategy=self.selection_strategy.value,
        )

        try:
            payload = self._client.search_items(
                query=search_query or None,
                jan_code=jan_code or None,
            )
        except YahooConfigError as exc:
            logger.warning("Yahoo search skipped: %s", exc)
            result.status = SEARCH_ERROR
            result.error_message = str(exc)
            return result
        except YahooApiError as exc:
            logger.warning("Yahoo API search failed: %s", exc.__class__.__name__)
            result.status = SEARCH_ERROR
            result.error_message = str(exc)
            return result

        parsed = self.parse_listings(payload, source_query=result.query)
        valid, rejected = validate_listings(parsed)
        ranked = self._matcher.match_and_rank(product, valid, exclude_invalid=True)

        result.listings = parsed
        result.valid_listings = ranked
        result.rejected_listings = rejected

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

        logger.info(
            "YahooMarketplace search for %r: total=%d valid=%d rejected=%d",
            product.name,
            len(parsed),
            len(ranked),
            len(rejected),
        )
        return result

    def parse_listings(self, data: Any, source_query: str = "") -> list[MarketplaceListing]:
        """
        Parse Yahoo API JSON payload into listings.

        Args:
            data: Parsed JSON response or injected payload for tests.
            source_query: Query label applied to listings.

        Returns:
            Parsed marketplace listings.
        """
        if isinstance(data, dict):
            return self._parser.parse(data, source_query=source_query)
        return []

    @staticmethod
    def _build_search_terms(product: Product, query: str | None) -> tuple[str, str]:
        if query and query.strip():
            return _normalize_query(query), ""

        jan_code = _extract_jan_code(product)
        if jan_code:
            return "", jan_code

        if product.brand.strip() and product.model.strip():
            return _normalize_query(f"{product.brand} {product.model}"), ""

        if product.brand.strip() and product.name.strip():
            return _normalize_query(f"{product.brand} {product.name}"), ""

        return _normalize_query(product.name), ""


def _normalize_query(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value.strip())
    return re.sub(r"\s+", " ", normalized)


def _extract_jan_code(product: Product) -> str:
    for candidate in (product.sku, product.model):
        text = candidate.strip()
        if _JAN_PATTERN.match(text):
            return text
    return ""


def create_yahoo_marketplace(
    settings: YahooApiSettings | None = None,
    client: YahooApiClient | None = None,
) -> YahooMarketplace:
    """
    Create YahooMarketplace from settings or injected client.

    Args:
        settings: Optional Yahoo settings override.
        client: Optional API client override.

    Returns:
        Configured YahooMarketplace instance.
    """
    api_client = client or YahooApiClient.from_settings(settings)
    return YahooMarketplace(client=api_client)
