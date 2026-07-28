"""
Demo provider for used luxury items (no network access).
"""

from typing import Any, Protocol, runtime_checkable

from config.constants import MARKETPLACE_USED_DEMO
from marketplace.amazon_price_normalizer import parse_jpy_price
from models.marketplace_listing import MarketplaceListing
from used_luxury.enrichment import UsedItemEnricher
from used_luxury.exceptions import UsedLuxuryParseError


@runtime_checkable
class UsedLuxuryProviderProtocol(Protocol):
    """Protocol for used luxury listing providers."""

    def search_items(self, *, query: str, page: int = 1, hits: int | None = None) -> dict[str, Any]:
        """Search used luxury listings from a configured data source."""
        ...


class FakeUsedLuxuryProvider:
    """In-memory used luxury provider for tests and demo mode."""

    def __init__(
        self,
        payload: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.payload = payload or {"items": [], "total_results": 0}
        self.error = error
        self.last_query: str = ""
        self.last_page: int = 1
        self.last_hits: int | None = None

    def search_items(self, *, query: str, page: int = 1, hits: int | None = None) -> dict[str, Any]:
        self.last_query = query
        self.last_page = page
        self.last_hits = hits
        if self.error is not None:
            raise self.error
        return self.payload

    def set_payload(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def set_error(self, error: Exception | None) -> None:
        self.error = error


class UsedLuxuryResponseParser:
    """Parse BrandProfitFinder internal used luxury JSON into listings."""

    def __init__(self, enricher: UsedItemEnricher | None = None) -> None:
        self._enricher = enricher or UsedItemEnricher()

    def parse(self, payload: dict[str, Any], source_query: str = "") -> list[MarketplaceListing]:
        """
        Parse internal standard JSON payload.

        Args:
            payload: Parsed JSON with items list.
            source_query: Query label for listings.

        Returns:
            List of MarketplaceListing with used_item_details populated.
        """
        items = payload.get("items")
        if items is None:
            return []
        if not isinstance(items, list):
            raise UsedLuxuryParseError("items must be a list when present")

        listings: list[MarketplaceListing] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            listing = self._parse_item(item, source_query=source_query)
            if listing is not None:
                listings.append(listing)
        return listings

    def parse_metadata(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Extract pagination metadata."""
        total = payload.get("total_results")
        page = payload.get("page")
        page_count = payload.get("page_count")
        parsed_page = page if isinstance(page, int) and page >= 1 else None
        parsed_page_count = page_count if isinstance(page_count, int) and page_count >= 0 else None
        has_next = (
            parsed_page is not None
            and parsed_page_count is not None
            and parsed_page < parsed_page_count
        )
        return {
            "total_results": total if isinstance(total, int) else None,
            "page": parsed_page,
            "page_count": parsed_page_count,
            "has_next_page": has_next,
            "next_page": str(parsed_page + 1) if has_next and parsed_page else None,
        }

    def _parse_item(self, item: dict[str, Any], source_query: str) -> MarketplaceListing | None:
        title = str(item.get("title") or "").strip()
        listing_id = str(item.get("listing_id") or "").strip()
        if not title and not listing_id:
            return None

        price = parse_jpy_price(item.get("price_jpy"))
        if price is None:
            return None

        shipping = parse_jpy_price(item.get("shipping_jpy"))
        shipping_unknown = item.get("shipping_jpy") is None and item.get("free_shipping") is not True
        if item.get("free_shipping") is True:
            shipping = price.__class__("0")  # Decimal(0)
            shipping_unknown = False

        listing_url = str(item.get("url") or "").strip()
        image_url = str(item.get("image_url") or "").strip()
        model_number = str(item.get("model_number") or "").strip()

        used_details = self._enricher.enrich(
            item,
            price_jpy=price,
            shipping_unknown=shipping_unknown,
            listing_url=listing_url,
            image_url=image_url,
            model_number=model_number,
        )

        legacy_condition = used_details.condition.value.lower()
        seller_rating = used_details.seller_details.seller_rating

        return MarketplaceListing(
            marketplace_name=str(item.get("marketplace_name") or MARKETPLACE_USED_DEMO),
            listing_id=listing_id or title,
            title=title or listing_id,
            brand=str(item.get("brand") or "").strip(),
            model_number=model_number,
            jan_code=str(item.get("jan_code") or "").strip(),
            condition=legacy_condition,
            price_jpy=price,
            shipping_jpy=shipping,
            shipping_unknown=shipping_unknown,
            seller_name=str(item.get("seller_name") or used_details.seller_details.business_name or "").strip(),
            seller_rating=seller_rating,
            listing_url=listing_url,
            image_url=image_url,
            source_query=source_query,
            used_item_details=used_details,
        )

    @staticmethod
    def validate_payload(payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            raise UsedLuxuryParseError("payload must be a JSON object")
        items = payload.get("items")
        if items is not None and not isinstance(items, list):
            raise UsedLuxuryParseError("items must be a list when present")
