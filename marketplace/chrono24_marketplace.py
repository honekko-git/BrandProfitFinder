"""
Chrono24 marketplace integration.
"""

import logging
import re
import unicodedata
from typing import Any

from config.constants import MARKETPLACE_CHRONO24
from marketplace.base_marketplace import BaseMarketplace
from marketplace.chrono24_client import Chrono24ClientProtocol
from marketplace.chrono24_exceptions import (
    Chrono24ClientError,
    Chrono24ConfigurationError,
    Chrono24ParseError,
    Chrono24ResponseError,
)
from marketplace.chrono24_response_parser import Chrono24ResponseParser
from marketplace.chrono24_settings import Chrono24Settings
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


class Chrono24Marketplace(BaseMarketplace):
    """Chrono24 marketplace (fixture/API-agnostic foundation)."""

    def __init__(
        self,
        client: Chrono24ClientProtocol | None = None,
        parser: Chrono24ResponseParser | None = None,
        matcher: ListingMatcher | None = None,
        settings: Chrono24Settings | None = None,
        selection_strategy: PriceSelectionStrategy = PriceSelectionStrategy.HIGHEST,
    ) -> None:
        self._client = client
        self._parser = parser or Chrono24ResponseParser()
        self._matcher = matcher or ListingMatcher()
        self._comparator = PriceComparator()
        self.settings = settings or Chrono24Settings.from_env()
        self.selection_strategy = selection_strategy

    @property
    def marketplace_name(self) -> str:
        return MARKETPLACE_CHRONO24

    def search(self, product: Product, query: str | None = None) -> MarketplaceSearchResult:
        """Search Chrono24 for listing candidates."""
        search_query = self._build_search_query(product, query)
        result = MarketplaceSearchResult(
            product=product,
            query=search_query,
            marketplace_name=self.marketplace_name,
            selection_strategy=self.selection_strategy.value,
        )

        if self._client is None:
            message = (
                "Chrono24 client is not configured. "
                "Use --demo-chrono24 for fixture demo mode."
            )
            logger.error(message)
            result.status = SEARCH_ERROR
            result.error_message = message
            return result

        if not search_query.strip():
            result.status = SEARCH_ERROR
            result.error_message = "empty search query"
            return result

        all_listings: list[MarketplaceListing] = []
        all_warnings: list[str] = []
        total_rejected = 0
        seen_ids: set[str] = set()
        max_pages = self.settings.validate_max_pages(self.settings.max_pages)
        page_size = self.settings.validate_page_size(self.settings.page_size)
        last_page_seen: int | None = None

        for page in range(1, max_pages + 1):
            try:
                payload = self._client.search_items(
                    search_query,
                    page=page,
                    page_size=page_size,
                )
                self._parser.validate_payload(payload)
            except Chrono24ResponseError as exc:
                logger.warning("Chrono24 response error on page %d: %s", page, exc)
                result.status = SEARCH_ERROR
                result.error_message = str(exc)
                return result
            except Chrono24ParseError as exc:
                logger.warning("Chrono24 parse error on page %d: %s", page, exc)
                result.status = SEARCH_ERROR
                result.error_message = str(exc)
                return result
            except Chrono24ClientError as exc:
                logger.warning("Chrono24 client error on page %d: %s", page, exc)
                result.status = SEARCH_ERROR
                result.error_message = str(exc)
                return result
            except Exception as exc:
                logger.warning(
                    "Chrono24 search failed on page %d: %s",
                    page,
                    exc.__class__.__name__,
                )
                result.status = SEARCH_ERROR
                result.error_message = "Chrono24 search failed"
                return result

            meta = self._parser.parse_metadata(payload)
            if last_page_seen == meta.get("page"):
                all_warnings.append(f"duplicate page {page}; stopping pagination")
                break
            last_page_seen = meta.get("page")

            parsed = self._parser.parse(
                payload,
                source_query=search_query,
                include_sold=self.settings.include_sold,
                include_reserved=self.settings.include_reserved,
                include_unavailable=self.settings.include_unavailable,
                include_discounted_only=self.settings.include_discounted_only,
                include_negotiable_only=self.settings.include_negotiable_only,
                require_verified_seller=self.settings.require_verified_seller,
                require_trusted_seller=self.settings.require_trusted_seller,
                include_private_sellers=self.settings.include_private_sellers,
                include_professional_dealers=self.settings.include_professional_dealers,
                allow_unknown_currency=self.settings.allow_unknown_currency,
                default_currency=self.settings.default_currency,
            )
            all_warnings.extend(parsed.warnings)
            total_rejected += parsed.rejected_count

            page_items = parsed.listings
            if not page_items:
                break

            added = 0
            for listing in page_items:
                if listing.listing_id in seen_ids:
                    total_rejected += 1
                    all_warnings.append(
                        f"skipped duplicate listing_id across pages: {listing.listing_id}"
                    )
                    continue
                seen_ids.add(listing.listing_id)
                all_listings.append(listing)
                added += 1

            if added == 0:
                break

            if meta.get("item_count", 0) == 0:
                break

        result.metadata = {
            "pages_fetched": min(page, max_pages),
            "warnings": all_warnings,
            "rejected_count": total_rejected,
            "valid_count": len(all_listings),
            "data_source": "fixture",
        }

        valid, rejected = validate_listings(all_listings)
        ranked = self._matcher.match_and_rank(product, valid, exclude_invalid=True)

        result.listings = all_listings
        result.valid_listings = ranked
        result.rejected_listings = rejected
        result.total_results = len(all_listings)

        if not all_listings:
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
            "Chrono24Marketplace search for %r: total=%d valid=%d rejected=%d warnings=%d",
            product.name,
            len(all_listings),
            len(ranked),
            total_rejected + len(rejected),
            len(all_warnings),
        )
        return result

    def parse_listings(self, data: Any, source_query: str = "") -> list[MarketplaceListing]:
        """Parse Chrono24 internal standard JSON into listings."""
        if isinstance(data, dict):
            parsed = self._parser.parse(
                data,
                source_query=source_query,
                include_sold=self.settings.include_sold,
                include_reserved=self.settings.include_reserved,
                include_unavailable=self.settings.include_unavailable,
                include_discounted_only=self.settings.include_discounted_only,
                include_negotiable_only=self.settings.include_negotiable_only,
                require_verified_seller=self.settings.require_verified_seller,
                require_trusted_seller=self.settings.require_trusted_seller,
                include_private_sellers=self.settings.include_private_sellers,
                include_professional_dealers=self.settings.include_professional_dealers,
                allow_unknown_currency=self.settings.allow_unknown_currency,
                default_currency=self.settings.default_currency,
            )
            return parsed.listings
        return []

    @staticmethod
    def _build_search_query(product: Product, query: str | None) -> str:
        if query and query.strip():
            return _normalize_query(query)
        jan_code = _extract_jan_code(product)
        if jan_code:
            return jan_code
        if product.brand.strip() and product.model.strip():
            return _normalize_query(f"{product.brand} {product.model}")
        if product.brand.strip() and product.name.strip():
            return _normalize_query(f"{product.brand} {product.name}")
        return _normalize_query(product.name)


def _normalize_query(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value.strip())
    return re.sub(r"\s+", " ", normalized)


def _extract_jan_code(product: Product) -> str:
    for candidate in (product.sku, product.model):
        text = candidate.strip()
        if _JAN_PATTERN.match(text):
            return text
    return ""


def create_chrono24_marketplace(
    client: Chrono24ClientProtocol | None = None,
    settings: Chrono24Settings | None = None,
) -> Chrono24Marketplace:
    """Create Chrono24Marketplace from config or injected client."""
    if client is None:
        raise Chrono24ConfigurationError(
            "Chrono24 client is not configured. "
            "Use --demo-chrono24 for fixture demo mode."
        )
    return Chrono24Marketplace(
        client=client,
        settings=settings or Chrono24Settings.from_env(),
    )
