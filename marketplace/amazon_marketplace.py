"""
Amazon.co.jp marketplace integration.
"""

import logging
import re
import unicodedata
from typing import Any

from config.constants import MARKETPLACE_AMAZON_JP
from marketplace.amazon_client import AmazonClientProtocol
from marketplace.amazon_exceptions import AmazonMarketplaceError, AmazonResponseParseError
from marketplace.amazon_response_parser import AmazonResponseParser
from marketplace.amazon_settings import AmazonConfig
from marketplace.base_marketplace import BaseMarketplace
from marketplace.listing_matcher import ListingMatcher
from marketplace.listing_validator import validate_listings
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


class AmazonMarketplace(BaseMarketplace):
    """Domestic marketplace implementation for Amazon.co.jp."""

    def __init__(
        self,
        client: AmazonClientProtocol | None = None,
        parser: AmazonResponseParser | None = None,
        matcher: ListingMatcher | None = None,
        config: AmazonConfig | None = None,
        selection_strategy: PriceSelectionStrategy = PriceSelectionStrategy.HIGHEST,
    ) -> None:
        """
        Initialize Amazon marketplace.

        Args:
            client: Amazon search client (injected for tests/demo).
            parser: Response parser.
            matcher: Listing matcher.
            config: Amazon configuration.
            selection_strategy: Domestic price selection strategy.
        """
        self._client = client
        self._parser = parser or AmazonResponseParser()
        self._matcher = matcher or ListingMatcher()
        self._comparator = PriceComparator()
        self.config = config or AmazonConfig.from_env()
        self.selection_strategy = selection_strategy

    @property
    def marketplace_name(self) -> str:
        return MARKETPLACE_AMAZON_JP

    def search(self, product: Product, query: str | None = None) -> MarketplaceSearchResult:
        """
        Search Amazon.co.jp for domestic listing candidates.

        Args:
            product: Overseas product to match.
            query: Optional query override.

        Returns:
            MarketplaceSearchResult with validated and ranked listings.
        """
        search_query = self._build_search_query(product, query)
        result = MarketplaceSearchResult(
            product=product,
            query=search_query,
            marketplace_name=self.marketplace_name,
            selection_strategy=self.selection_strategy.value,
        )

        if self._client is None:
            message = "Amazon marketplace is not configured; skipping Amazon search."
            logger.warning(message)
            result.status = SEARCH_ERROR
            result.error_message = message
            return result

        try:
            payload = self._client.search_items(
                query=search_query,
                max_results=self.config.max_results,
            )
            self._parser.validate_payload(payload)
        except AmazonResponseParseError as exc:
            logger.warning("Amazon response parse failed: %s", exc)
            result.status = SEARCH_ERROR
            result.error_message = str(exc)
            return result
        except AmazonMarketplaceError as exc:
            logger.warning("Amazon search failed: %s", exc)
            result.status = SEARCH_ERROR
            result.error_message = str(exc)
            return result
        except Exception as exc:
            logger.warning("Amazon search failed: %s", exc.__class__.__name__)
            result.status = SEARCH_ERROR
            result.error_message = "Amazon search failed"
            return result

        total_results, next_page_token = self._parser.parse_metadata(payload)
        result.total_results = total_results
        result.next_page_token = next_page_token
        result.metadata = {
            "marketplace_id": self.config.marketplace_id,
            "currency": self.config.default_currency,
        }

        parsed = self.parse_listings(payload, source_query=search_query)
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
            "AmazonMarketplace search for %r: total=%d valid=%d rejected=%d",
            product.name,
            len(parsed),
            len(ranked),
            len(rejected),
        )
        return result

    def parse_listings(self, data: Any, source_query: str = "") -> list[MarketplaceListing]:
        """
        Parse Amazon JSON payload into listings.

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


def create_amazon_marketplace(
    client: AmazonClientProtocol | None = None,
    config: AmazonConfig | None = None,
) -> AmazonMarketplace:
    """
    Create AmazonMarketplace from config or injected client.

    Args:
        client: Optional Amazon client override.
        config: Optional configuration override.

    Returns:
        Configured AmazonMarketplace instance.
    """
    return AmazonMarketplace(client=client, config=config or AmazonConfig.from_env())
