"""
Yahoo Shopping API response parser.
"""

import logging
from decimal import Decimal, InvalidOperation
from typing import Any

from config.constants import MARKETPLACE_YAHOO
from models.marketplace_listing import MarketplaceListing

logger = logging.getLogger(__name__)


class YahooResponseParser:
    """Parse Yahoo itemSearch JSON responses into marketplace listings."""

    def parse(self, payload: dict[str, object], source_query: str = "") -> list[MarketplaceListing]:
        """
        Parse a Yahoo itemSearch response.

        Args:
            payload: Parsed JSON response.
            source_query: Query or JAN used for the search.

        Returns:
            Parsed marketplace listings. Invalid hits are included with safe defaults.
        """
        hits = payload.get("hits")
        if hits is None:
            return []
        if not isinstance(hits, list):
            logger.warning("Yahoo hits field is not a list")
            return []

        listings: list[MarketplaceListing] = []
        for hit in hits:
            if not isinstance(hit, dict):
                logger.warning("Skipping Yahoo hit with invalid type")
                continue
            listing = self._parse_hit(hit, source_query=source_query)
            if listing is not None:
                listings.append(listing)

        return listings

    def _parse_hit(self, hit: dict[str, Any], source_query: str) -> MarketplaceListing | None:
        title = str(hit.get("name") or "").strip()
        code = str(hit.get("code") or "").strip()
        jan_code = str(hit.get("janCode") or "").strip()
        price_jpy = self._parse_decimal(hit.get("price"))
        shipping_jpy = self._parse_shipping(hit.get("shipping"))
        brand = self._parse_brand(hit.get("brand"))
        seller_name, seller_rating = self._parse_seller(hit.get("seller"))
        listing_url = str(hit.get("url") or "").strip()
        image_url = self._parse_image(hit.get("image"))
        condition = str(hit.get("condition") or "new").strip()
        availability = "in_stock" if hit.get("inStock") is True else "unknown"
        if hit.get("inStock") is False:
            availability = "out_of_stock"

        review_count = self._parse_review_count(hit.get("review"))

        if not title and not code:
            logger.warning("Skipping Yahoo hit without title and code")
            return None

        return MarketplaceListing(
            marketplace_name=MARKETPLACE_YAHOO,
            listing_id=code or title,
            title=title or code,
            brand=brand,
            model_number="",
            sku=code,
            jan_code=jan_code,
            condition=condition,
            price_jpy=price_jpy if price_jpy is not None else Decimal("0"),
            shipping_jpy=shipping_jpy if shipping_jpy is not None else Decimal("0"),
            seller_name=seller_name,
            seller_rating=seller_rating,
            listing_url=listing_url,
            image_url=image_url,
            availability=availability,
            sold_count=review_count,
            source_query=source_query,
        )

    @staticmethod
    def _parse_decimal(value: Any) -> Decimal | None:
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def _parse_shipping(shipping_data: Any) -> Decimal | None:
        if isinstance(shipping_data, dict):
            price = shipping_data.get("price")
            if price is not None:
                return YahooResponseParser._parse_decimal(price)
        return Decimal("0")

    @staticmethod
    def _parse_brand(brand_data: Any) -> str:
        if isinstance(brand_data, dict):
            return str(brand_data.get("name") or "").strip()
        if isinstance(brand_data, str):
            return brand_data.strip()
        return ""

    @staticmethod
    def _parse_seller(seller_data: Any) -> tuple[str, Decimal | None]:
        if not isinstance(seller_data, dict):
            return "", None
        name = str(seller_data.get("name") or "").strip()
        review = seller_data.get("review")
        rating = None
        if isinstance(review, dict):
            rating = YahooResponseParser._parse_decimal(review.get("rate"))
        return name, rating

    @staticmethod
    def _parse_image(image_data: Any) -> str:
        if isinstance(image_data, dict):
            medium = str(image_data.get("medium") or "").strip()
            if medium:
                return medium
            return str(image_data.get("small") or "").strip()
        if isinstance(image_data, str):
            return image_data.strip()
        return ""

    @staticmethod
    def _parse_review_count(review_data: Any) -> int | None:
        if isinstance(review_data, dict):
            count = review_data.get("count")
            if isinstance(count, int) and count >= 0:
                return count
        return None
