"""
Yahoo Auction marketplace integration.
"""

import logging
import re
import unicodedata
from typing import Any

from config.constants import MARKETPLACE_YAHOO_AUCTION
from marketplace.base_marketplace import BaseMarketplace
from marketplace.listing_matcher import ListingMatcher
from marketplace.listing_validator import validate_listings
from marketplace.yahoo_auction_client import YahooAuctionClientProtocol
from marketplace.yahoo_auction_exceptions import (
    YahooAuctionMarketplaceError,
    YahooAuctionResponseError,
)
from marketplace.yahoo_auction_response_parser import YahooAuctionResponseParser
from marketplace.yahoo_auction_settings import YahooAuctionConfig
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


class YahooAuctionMarketplace(BaseMarketplace):
    """Domestic marketplace implementation for Yahoo Auction (fixture/API-agnostic)."""

    def __init__(
        self,
        client: YahooAuctionClientProtocol | None = None,
        parser: YahooAuctionResponseParser | None = None,
        matcher: ListingMatcher | None = None,
        config: YahooAuctionConfig | None = None,
        selection_strategy: PriceSelectionStrategy = PriceSelectionStrategy.HIGHEST,
    ) -> None:
        """
        Initialize Yahoo Auction marketplace.

        Args:
            client: Yahoo Auction search client (injected for tests/demo).
            parser: Response parser.
            matcher: Listing matcher.
            config: Yahoo Auction configuration.
            selection_strategy: Domestic price selection strategy.
        """
        self._client = client
        self._parser = parser or YahooAuctionResponseParser()
        self._matcher = matcher or ListingMatcher()
        self._comparator = PriceComparator()
        self.config = config or YahooAuctionConfig.from_env()
        self.selection_strategy = selection_strategy

    @property
    def marketplace_name(self) -> str:
        return MARKETPLACE_YAHOO_AUCTION

    def search(self, product: Product, query: str | None = None) -> MarketplaceSearchResult:
        """
        Search Yahoo Auction for domestic listing candidates.

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
            message = "Yahoo Auction live data source is not configured; skipping search."
            logger.warning(message)
            result.status = SEARCH_ERROR
            result.error_message = message
            return result

        try:
            payload = self._client.search_items(
                query=search_query,
                hits=self.config.hits,
            )
            self._parser.validate_payload(payload)
        except YahooAuctionResponseError as exc:
            logger.warning("Yahoo Auction response parse failed: %s", exc)
            result.status = SEARCH_ERROR
            result.error_message = str(exc)
            return result
        except YahooAuctionMarketplaceError as exc:
            logger.warning("Yahoo Auction search failed: %s", exc)
            result.status = SEARCH_ERROR
            result.error_message = str(exc)
            return result
        except Exception as exc:
            logger.warning("Yahoo Auction search failed: %s", exc.__class__.__name__)
            result.status = SEARCH_ERROR
            result.error_message = "Yahoo Auction search failed"
            return result

        meta = self._parser.parse_metadata(payload)
        result.total_results = meta.get("total_results")
        result.next_page_token = meta.get("next_page")
        result.metadata = {
            "page": meta.get("page"),
            "page_count": meta.get("page_count"),
            "has_next_page": meta.get("has_next_page"),
            "sort": self.config.sort,
            "data_source": self.config.data_source or "fixture",
            "note": (
                "current_price on active auctions is provisional and not a confirmed sold price"
            ),
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
            "YahooAuctionMarketplace search for %r: total=%d valid=%d rejected=%d",
            product.name,
            len(parsed),
            len(ranked),
            len(rejected),
        )
        return result

    def parse_listings(self, data: Any, source_query: str = "") -> list[MarketplaceListing]:
        """
        Parse Yahoo Auction JSON payload into listings.

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


def create_yahoo_auction_marketplace(
    client: YahooAuctionClientProtocol | None = None,
    config: YahooAuctionConfig | None = None,
) -> YahooAuctionMarketplace:
    """
    Create YahooAuctionMarketplace from config or injected client.

    Args:
        client: Optional Yahoo Auction client override.
        config: Optional configuration override.

    Returns:
        Configured YahooAuctionMarketplace instance.
    """
    return YahooAuctionMarketplace(client=client, config=config or YahooAuctionConfig.from_env())
