"""
Amazon internal standard response parser.
"""

import logging
from decimal import Decimal
from typing import Any

from config.constants import CURRENCY_JPY, MARKETPLACE_AMAZON_JP
from marketplace.amazon_exceptions import AmazonResponseParseError
from marketplace.amazon_price_normalizer import parse_jpy_price
from models.marketplace_listing import MarketplaceListing

logger = logging.getLogger(__name__)

_CONDITION_MAP = {
    "NEW": "new",
    "USED": "used",
    "UNKNOWN": "unknown",
}


class AmazonResponseParser:
    """Parse Amazon internal standard JSON into marketplace listings."""

    def parse(self, payload: dict[str, object], source_query: str = "") -> list[MarketplaceListing]:
        """
        Parse an Amazon search response payload.

        Args:
            payload: Internal standard JSON response.
            source_query: Query label applied to listings.

        Returns:
            Parsed marketplace listings. Invalid items are skipped.
        """
        if not isinstance(payload, dict):
            logger.warning("Amazon payload is not a JSON object")
            return []

        items = payload.get("items")
        if items is None:
            return []
        if not isinstance(items, list):
            logger.warning("Amazon items field is not a list")
            return []

        listings: list[MarketplaceListing] = []
        for item in items:
            if item is None:
                logger.warning("Skipping null Amazon item")
                continue
            if not isinstance(item, dict):
                logger.warning("Skipping Amazon item with invalid type")
                continue
            listing = self._parse_item(item, source_query=source_query)
            if listing is not None:
                listings.append(listing)

        return listings

    def parse_metadata(self, payload: dict[str, object]) -> tuple[int | None, str | None]:
        """
        Extract pagination metadata from payload.

        Args:
            payload: Internal standard JSON response.

        Returns:
            Tuple of (total_results, next_page_token).
        """
        total_results = payload.get("total_results")
        next_page_token = payload.get("next_page_token")
        parsed_total = total_results if isinstance(total_results, int) and total_results >= 0 else None
        parsed_token = str(next_page_token) if next_page_token else None
        return parsed_total, parsed_token

    def _parse_item(self, item: dict[str, Any], source_query: str) -> MarketplaceListing | None:
        title = str(item.get("title") or "").strip()
        asin = str(item.get("asin") or item.get("item_identifier") or "").strip()
        brand = str(item.get("brand") or "").strip()
        model_number = str(item.get("model_number") or "").strip()
        jan_code = str(item.get("jan_code") or "").strip()
        listing_url = str(item.get("detail_page_url") or item.get("url") or "").strip()
        image_url = str(item.get("image_url") or "").strip()

        price_jpy = self._parse_price(item.get("price"))
        if price_jpy is None:
            logger.warning("Skipping Amazon item without valid JPY price (asin=%r)", asin or title)
            return None

        if not title and not asin:
            logger.warning("Skipping Amazon item without title and ASIN")
            return None

        shipping_jpy, shipping_unknown = self._parse_shipping(item.get("shipping"))
        seller_name, is_amazon_seller = self._parse_seller(item.get("seller"))
        condition = self._parse_condition(item.get("condition"))
        availability = str(item.get("availability") or "").strip().lower().replace("_", " ")
        is_prime = bool(item.get("is_prime") is True)
        points = self._parse_points(item.get("points"))
        currency = self._parse_currency(item.get("price"))

        metadata = {
            "asin": asin,
            "is_prime": is_prime,
            "is_amazon_seller": is_amazon_seller,
            "points": float(points) if points is not None else None,
            "shipping_unknown": shipping_unknown,
        }

        return MarketplaceListing(
            marketplace_name=MARKETPLACE_AMAZON_JP,
            listing_id=asin or title,
            title=title or asin,
            brand=brand,
            model_number=model_number,
            sku=asin,
            jan_code=jan_code,
            condition=condition,
            price_jpy=price_jpy,
            shipping_jpy=shipping_jpy,
            shipping_unknown=shipping_unknown,
            seller_name=seller_name,
            listing_url=listing_url,
            image_url=image_url,
            availability=availability,
            source_query=source_query,
            currency=currency,
            points_jpy=points,
            is_prime=is_prime,
            is_amazon_seller=is_amazon_seller,
            source_metadata=metadata,
        )

    @staticmethod
    def _parse_price(price_data: Any) -> Decimal | None:
        if isinstance(price_data, dict):
            currency = str(price_data.get("currency") or CURRENCY_JPY).strip().upper()
            if currency and currency != CURRENCY_JPY:
                logger.warning("Skipping Amazon item with non-JPY currency: %s", currency)
                return None
            return parse_jpy_price(price_data.get("amount"))
        return parse_jpy_price(price_data)

    @staticmethod
    def _parse_currency(price_data: Any) -> str:
        if isinstance(price_data, dict):
            currency = str(price_data.get("currency") or CURRENCY_JPY).strip().upper()
            return currency or CURRENCY_JPY
        return CURRENCY_JPY

    @staticmethod
    def _parse_shipping(shipping_data: Any) -> tuple[Decimal | None, bool]:
        if shipping_data is None:
            return None, True
        if not isinstance(shipping_data, dict):
            return None, True

        if shipping_data.get("is_free") is True:
            return Decimal("0"), False

        amount = shipping_data.get("amount")
        if amount is None:
            return None, True

        parsed = parse_jpy_price(amount)
        if parsed is None:
            return None, True
        return parsed, False

    @staticmethod
    def _parse_seller(seller_data: Any) -> tuple[str, bool]:
        if not isinstance(seller_data, dict):
            return "", False
        name = str(seller_data.get("name") or "").strip()
        is_amazon = bool(seller_data.get("is_amazon") is True)
        return name, is_amazon

    @staticmethod
    def _parse_points(value: Any) -> Decimal | None:
        if value is None:
            return None
        if value == 0 or value == "0":
            return Decimal("0")
        return parse_jpy_price(value)

    @staticmethod
    def _parse_condition(value: Any) -> str:
        if value is None:
            return "unknown"
        normalized = str(value).strip().upper()
        return _CONDITION_MAP.get(normalized, normalized.lower() or "unknown")

    @staticmethod
    def validate_payload(payload: dict[str, object]) -> None:
        """
        Validate top-level payload structure.

        Args:
            payload: Response payload.

        Raises:
            AmazonResponseParseError: When payload structure is invalid.
        """
        if not isinstance(payload, dict):
            raise AmazonResponseParseError("Amazon payload must be a JSON object")
        items = payload.get("items")
        if items is not None and not isinstance(items, list):
            raise AmazonResponseParseError("Amazon items must be a list when present")
