"""
Rakuten Ichiba Item Search API response parser (formatVersion=2).
"""

import logging
from decimal import Decimal, InvalidOperation
from typing import Any

from config.constants import CURRENCY_JPY, MARKETPLACE_RAKUTEN
from marketplace.amazon_price_normalizer import parse_jpy_price
from marketplace.rakuten_exceptions import RakutenResponseError
from models.marketplace_listing import MarketplaceListing

logger = logging.getLogger(__name__)

_USED_KEYWORDS = ("中古", "used")


class RakutenResponseParser:
    """Parse Rakuten Ichiba search JSON into marketplace listings."""

    def parse(self, payload: dict[str, object], source_query: str = "") -> list[MarketplaceListing]:
        """
        Parse a Rakuten item search response.

        Args:
            payload: Parsed JSON response (formatVersion=2).
            source_query: Query label applied to listings.

        Returns:
            Parsed marketplace listings. Invalid items are skipped.
        """
        if not isinstance(payload, dict):
            logger.warning("Rakuten payload is not a JSON object")
            return []

        items = payload.get("Items")
        if items is None:
            items = payload.get("items")
        if items is None:
            return []
        if not isinstance(items, list):
            logger.warning("Rakuten items field is not a list")
            return []

        listings: list[MarketplaceListing] = []
        for item in items:
            if item is None:
                logger.warning("Skipping null Rakuten item")
                continue
            record = self._unwrap_item(item)
            if record is None:
                continue
            listing = self._parse_item(record, source_query=source_query)
            if listing is not None:
                listings.append(listing)

        return listings

    def parse_metadata(self, payload: dict[str, object]) -> dict[str, Any]:
        """
        Extract pagination metadata from payload.

        Args:
            payload: Parsed JSON response.

        Returns:
            Metadata dictionary with count, page, page_count, has_next_page.
        """
        count = payload.get("count")
        page = payload.get("page")
        page_count = payload.get("pageCount")
        parsed_count = count if isinstance(count, int) and count >= 0 else None
        parsed_page = page if isinstance(page, int) and page >= 1 else None
        parsed_page_count = page_count if isinstance(page_count, int) and page_count >= 0 else None
        has_next = (
            parsed_page is not None
            and parsed_page_count is not None
            and parsed_page < parsed_page_count
        )
        next_page = str(parsed_page + 1) if has_next and parsed_page is not None else None
        return {
            "count": parsed_count,
            "page": parsed_page,
            "page_count": parsed_page_count,
            "has_next_page": has_next,
            "next_page": next_page,
        }

    def _unwrap_item(self, item: Any) -> dict[str, Any] | None:
        if isinstance(item, dict):
            nested = item.get("Item")
            if isinstance(nested, dict):
                return nested
            return item
        logger.warning("Skipping Rakuten item with invalid type")
        return None

    def _parse_item(self, item: dict[str, Any], source_query: str) -> MarketplaceListing | None:
        title = str(item.get("itemName") or "").strip()
        item_code = str(item.get("itemCode") or "").strip()
        price_jpy = parse_jpy_price(item.get("itemPrice"))
        if price_jpy is None:
            logger.warning("Skipping Rakuten item without valid price (code=%r)", item_code or title)
            return None

        if not title and not item_code:
            logger.warning("Skipping Rakuten item without title and itemCode")
            return None

        listing_url = str(item.get("itemUrl") or "").strip()
        image_url = self._parse_image_url(item)
        seller_name = str(item.get("shopName") or "").strip()
        shop_code = str(item.get("shopCode") or "").strip()
        shipping_jpy, shipping_unknown = self._parse_postage(item.get("postageFlag"))
        condition = self._parse_condition(title, item.get("itemCaption"), item.get("catchcopy"))
        availability = self._parse_availability(item.get("availability"))
        review_count = self._parse_int(item.get("reviewCount"))
        review_average = self._parse_decimal(item.get("reviewAverage"))
        point_rate = self._parse_decimal(item.get("pointRate"))

        metadata = {
            "item_code": item_code,
            "shop_code": shop_code,
            "shop_name": seller_name,
            "catchcopy": str(item.get("catchcopy") or "").strip() or None,
            "item_caption": str(item.get("itemCaption") or "").strip() or None,
            "genre_id": str(item.get("genreId") or "").strip() or None,
            "tag_ids": item.get("tagIds") if isinstance(item.get("tagIds"), list) else [],
            "review_count": review_count,
            "review_average": float(review_average) if review_average is not None else None,
            "point_rate": float(point_rate) if point_rate is not None else None,
            "postage_flag": item.get("postageFlag"),
            "tax_flag": item.get("taxFlag"),
            "credit_card_flag": item.get("creditCardFlag"),
            "availability": item.get("availability"),
            "affiliate_url": str(item.get("affiliateUrl") or "").strip() or None,
            "shipping_unknown": shipping_unknown,
        }

        return MarketplaceListing(
            marketplace_name=MARKETPLACE_RAKUTEN,
            listing_id=item_code or title,
            title=title or item_code,
            brand="",
            model_number="",
            sku=item_code,
            jan_code="",
            condition=condition,
            price_jpy=price_jpy,
            shipping_jpy=shipping_jpy,
            shipping_unknown=shipping_unknown,
            seller_name=seller_name,
            seller_rating=review_average,
            listing_url=listing_url,
            image_url=image_url,
            availability=availability,
            sold_count=review_count,
            source_query=source_query,
            currency=CURRENCY_JPY,
            point_rate=point_rate,
            source_metadata=metadata,
        )

    @staticmethod
    def _parse_image_url(item: dict[str, Any]) -> str:
        medium = item.get("mediumImageUrls")
        if isinstance(medium, list) and medium:
            first = medium[0]
            if isinstance(first, dict):
                return str(first.get("imageUrl") or "").strip()
            if isinstance(first, str):
                return first.strip()
        small = item.get("smallImageUrls")
        if isinstance(small, list) and small:
            first = small[0]
            if isinstance(first, dict):
                return str(first.get("imageUrl") or "").strip()
            if isinstance(first, str):
                return first.strip()
        return ""

    @staticmethod
    def _parse_postage(postage_flag: Any) -> tuple[Decimal | None, bool]:
        if postage_flag is None:
            return None, True
        try:
            flag = int(postage_flag)
        except (TypeError, ValueError):
            return None, True
        if flag == 0:
            return Decimal("0"), False
        return None, True

    @staticmethod
    def _parse_condition(title: str, caption: Any, catchcopy: Any) -> str:
        combined = " ".join(
            part for part in (title, str(caption or ""), str(catchcopy or "")) if part
        ).lower()
        if any(keyword in combined for keyword in _USED_KEYWORDS):
            return "used"
        return "new"

    @staticmethod
    def _parse_availability(value: Any) -> str:
        if value == 1 or value == "1":
            return "in_stock"
        if value == 0 or value == "0":
            return "out_of_stock"
        return "unknown"

    @staticmethod
    def _parse_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed >= 0 else None

    @staticmethod
    def _parse_decimal(value: Any) -> Decimal | None:
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def validate_payload(payload: dict[str, object]) -> None:
        """
        Validate top-level payload structure.

        Args:
            payload: Response payload.

        Raises:
            RakutenResponseError: When payload structure is invalid.
        """
        if not isinstance(payload, dict):
            raise RakutenResponseError("Rakuten payload must be a JSON object")
        items = payload.get("Items")
        if items is None:
            items = payload.get("items")
        if items is not None and not isinstance(items, list):
            raise RakutenResponseError("Rakuten items must be a list when present")
