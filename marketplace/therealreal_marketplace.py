"""
The RealReal marketplace integration.
"""

import logging
import re
import unicodedata
from typing import Any

from config.constants import MARKETPLACE_THEREALREAL
from marketplace.base_marketplace import BaseMarketplace
from marketplace.listing_matcher import ListingMatcher
from marketplace.listing_validator import validate_listings
from marketplace.therealreal_client import TheRealRealClientProtocol
from marketplace.therealreal_exceptions import (
    TheRealRealClientError,
    TheRealRealConfigurationError,
    TheRealRealParseError,
    TheRealRealResponseError,
)
from marketplace.therealreal_response_parser import TheRealRealResponseParser
from marketplace.therealreal_settings import TheRealRealSettings
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


class TheRealRealMarketplace(BaseMarketplace):
    """The RealReal marketplace (fixture/API-agnostic foundation)."""

    def __init__(
        self,
        client: TheRealRealClientProtocol | None = None,
        parser: TheRealRealResponseParser | None = None,
        matcher: ListingMatcher | None = None,
        settings: TheRealRealSettings | None = None,
        selection_strategy: PriceSelectionStrategy = PriceSelectionStrategy.HIGHEST,
    ) -> None:
        self._client = client
        self._parser = parser or TheRealRealResponseParser()
        self._matcher = matcher or ListingMatcher()
        self._comparator = PriceComparator()
        self.settings = settings or TheRealRealSettings.from_env()
        self.selection_strategy = selection_strategy

    @property
    def marketplace_name(self) -> str:
        return MARKETPLACE_THEREALREAL

    def search(self, product: Product, query: str | None = None) -> MarketplaceSearchResult:
        """Search The RealReal for listing candidates."""
        search_query = self._build_search_query(product, query)
        result = MarketplaceSearchResult(
            product=product,
            query=search_query,
            marketplace_name=self.marketplace_name,
            selection_strategy=self.selection_strategy.value,
        )

        if self._client is None:
            message = (
                "The RealReal client is not configured. "
                "Use --demo-therealreal for fixture demo mode."
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
            except TheRealRealResponseError as exc:
                logger.warning("The RealReal response error on page %d: %s", page, exc)
                result.status = SEARCH_ERROR
                result.error_message = str(exc)
                return result
            except TheRealRealParseError as exc:
                logger.warning("The RealReal parse error on page %d: %s", page, exc)
                result.status = SEARCH_ERROR
                result.error_message = str(exc)
                return result
            except TheRealRealClientError as exc:
                logger.warning("The RealReal client error on page %d: %s", page, exc)
                result.status = SEARCH_ERROR
                result.error_message = str(exc)
                return result
            except Exception as exc:
                logger.warning(
                    "The RealReal search failed on page %d: %s",
                    page,
                    exc.__class__.__name__,
                )
                result.status = SEARCH_ERROR
                result.error_message = "The RealReal search failed"
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
                include_final_sale=self.settings.include_final_sale,
                include_discounted_only=self.settings.include_discounted_only,
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
            "TheRealRealMarketplace search for %r: total=%d valid=%d rejected=%d warnings=%d",
            product.name,
            len(all_listings),
            len(ranked),
            total_rejected + len(rejected),
            len(all_warnings),
        )
        return result

    def parse_listings(self, data: Any, source_query: str = "") -> list[MarketplaceListing]:
        """Parse The RealReal internal standard JSON into listings."""
        if isinstance(data, dict):
            parsed = self._parser.parse(
                data,
                source_query=source_query,
                include_sold=self.settings.include_sold,
                include_reserved=self.settings.include_reserved,
                include_unavailable=self.settings.include_unavailable,
                include_final_sale=self.settings.include_final_sale,
                include_discounted_only=self.settings.include_discounted_only,
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


def create_therealreal_marketplace(
    client: TheRealRealClientProtocol | None = None,
    settings: TheRealRealSettings | None = None,
) -> TheRealRealMarketplace:
    """Create TheRealRealMarketplace from config or injected client."""
    if client is None:
        raise TheRealRealConfigurationError(
            "The RealReal client is not configured. "
            "Use --demo-therealreal for fixture demo mode."
        )
    return TheRealRealMarketplace(
        client=client,
        settings=settings or TheRealRealSettings.from_env(),
    )
