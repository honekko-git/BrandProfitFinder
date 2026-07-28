"""
Yahoo Auction internal standard response parser.
"""

import logging
from decimal import Decimal
from typing import Any

from config.constants import CURRENCY_JPY, MARKETPLACE_YAHOO_AUCTION
from marketplace.amazon_price_normalizer import parse_jpy_price
from marketplace.yahoo_auction_exceptions import YahooAuctionResponseError
from models.marketplace_listing import MarketplaceListing

logger = logging.getLogger(__name__)

_CONDITION_MAP = {
    "new": "new",
    "unused": "new",
    "used": "used",
    "preowned": "used",
    "second_hand": "used",
    "unknown": "unknown",
}

_LISTING_STATUS_MAP = {
    "active": "active",
    "sold": "sold",
    "ended": "ended",
    "unknown": "unknown",
}

_AUCTION_TYPE_MAP = {
    "auction": "auction",
    "buy_now": "buy_now",
    "auction_with_buy_now": "auction_with_buy_now",
    "unknown": "unknown",
}


class YahooAuctionResponseParser:
    """Parse Yahoo Auction internal standard JSON into marketplace listings."""

    def parse(self, payload: dict[str, object], source_query: str = "") -> list[MarketplaceListing]:
        """
        Parse an internal standard Yahoo Auction search payload.

        Args:
            payload: BrandProfitFinder internal standard JSON (not a live API shape).
            source_query: Query label applied to listings.

        Returns:
            Parsed marketplace listings. Invalid items are skipped.
        """
        if not isinstance(payload, dict):
            logger.warning("Yahoo Auction payload is not a JSON object")
            return []

        items = payload.get("items")
        if items is None:
            return []
        if not isinstance(items, list):
            logger.warning("Yahoo Auction items field is not a list")
            return []

        listings: list[MarketplaceListing] = []
        for item in items:
            if item is None:
                logger.warning("Skipping null Yahoo Auction item")
                continue
            if not isinstance(item, dict):
                logger.warning("Skipping Yahoo Auction item with invalid type")
                continue
            listing = self._parse_item(item, source_query=source_query)
            if listing is not None:
                listings.append(listing)

        return listings

    def parse_metadata(self, payload: dict[str, object]) -> dict[str, Any]:
        """
        Extract pagination metadata from payload.

        Args:
            payload: Internal standard JSON response.

        Returns:
            Metadata dictionary with count, page, page_count, has_next_page, next_page.
        """
        total = payload.get("total_results")
        page = payload.get("page")
        page_count = payload.get("page_count")
        parsed_total = total if isinstance(total, int) and total >= 0 else None
        parsed_page = page if isinstance(page, int) and page >= 1 else None
        parsed_page_count = page_count if isinstance(page_count, int) and page_count >= 0 else None
        has_next = (
            parsed_page is not None
            and parsed_page_count is not None
            and parsed_page < parsed_page_count
        )
        next_page = str(parsed_page + 1) if has_next and parsed_page is not None else None
        return {
            "total_results": parsed_total,
            "page": parsed_page,
            "page_count": parsed_page_count,
            "has_next_page": has_next,
            "next_page": next_page,
        }

    def _parse_item(self, item: dict[str, Any], source_query: str) -> MarketplaceListing | None:
        title = str(item.get("title") or "").strip()
        auction_id = str(item.get("auction_id") or "").strip()
        brand = str(item.get("brand") or "").strip()
        model_number = str(item.get("model_number") or "").strip()
        jan_code = str(item.get("jan_code") or "").strip()
        listing_url = str(item.get("url") or "").strip()
        image_url = str(item.get("image_url") or "").strip()
        seller_name = str(item.get("seller_name") or "").strip()

        current_price = parse_jpy_price(item.get("current_price"))
        buy_now_price = parse_jpy_price(item.get("buy_now_price"))
        winning_price = parse_jpy_price(item.get("winning_price"))

        listing_status = self._normalize_listing_status(item.get("listing_status"))
        auction_type = self._normalize_auction_type(item.get("auction_type"))
        condition = self._normalize_condition(item.get("condition"))

        price_jpy, price_source = self._select_price(
            listing_status=listing_status,
            current_price=current_price,
            buy_now_price=buy_now_price,
            winning_price=winning_price,
            auction_id=auction_id or title,
        )
        if price_jpy is None:
            logger.warning(
                "Skipping Yahoo Auction item without selectable price (auction_id=%r)",
                auction_id or title,
            )
            return None

        if not title and not auction_id:
            logger.warning("Skipping Yahoo Auction item without title and auction_id")
            return None

        shipping_jpy, shipping_unknown = self._parse_shipping(item)
        availability = self._availability_from_status(listing_status)
        bid_count = self._parse_int(item.get("bid_count"))
        watch_count = self._parse_int(item.get("watch_count"))

        nested_meta = item.get("source_metadata")
        extra_meta = dict(nested_meta) if isinstance(nested_meta, dict) else {}

        metadata: dict[str, Any] = {
            "auction_id": auction_id,
            "seller_id": str(item.get("seller_id") or "").strip() or None,
            "current_price_jpy": float(current_price) if current_price is not None else None,
            "buy_now_price_jpy": float(buy_now_price) if buy_now_price is not None else None,
            "winning_price_jpy": float(winning_price) if winning_price is not None else None,
            "price_source": price_source,
            "listing_status": listing_status,
            "auction_type": auction_type,
            "bid_count": bid_count,
            "watch_count": watch_count,
            "start_time": str(item.get("start_time") or "").strip() or None,
            "end_time": str(item.get("end_time") or "").strip() or None,
            "tax_included": item.get("tax_included"),
            "free_shipping": item.get("free_shipping"),
            "shipping_unknown": shipping_unknown,
            "price_is_provisional": listing_status == "active" and price_source == "current_price",
            **extra_meta,
        }

        return MarketplaceListing(
            marketplace_name=MARKETPLACE_YAHOO_AUCTION,
            listing_id=auction_id or title,
            title=title or auction_id,
            brand=brand,
            model_number=model_number,
            sku="",
            jan_code=jan_code,
            condition=condition,
            price_jpy=price_jpy,
            shipping_jpy=shipping_jpy,
            shipping_unknown=shipping_unknown,
            seller_name=seller_name,
            listing_url=listing_url,
            image_url=image_url,
            availability=availability,
            sold_count=bid_count,
            source_query=source_query,
            currency=str(item.get("currency") or CURRENCY_JPY).strip().upper() or CURRENCY_JPY,
            source_metadata=metadata,
        )

    @staticmethod
    def _select_price(
        *,
        listing_status: str,
        current_price: Decimal | None,
        buy_now_price: Decimal | None,
        winning_price: Decimal | None,
        auction_id: str,
    ) -> tuple[Decimal | None, str | None]:
        if listing_status == "sold":
            if winning_price is not None:
                return winning_price, "winning_price"
            logger.warning(
                "Skipping sold Yahoo Auction item without winning_price (auction_id=%r)",
                auction_id,
            )
            return None, None

        if buy_now_price is not None:
            return buy_now_price, "buy_now_price"
        if current_price is not None:
            return current_price, "current_price"
        return None, None

    @staticmethod
    def _parse_shipping(item: dict[str, Any]) -> tuple[Decimal | None, bool]:
        if item.get("free_shipping") is True:
            return Decimal("0"), False

        shipping_price = parse_jpy_price(item.get("shipping_price"))
        if shipping_price is not None:
            return shipping_price, False

        return None, True

    @staticmethod
    def _normalize_condition(value: Any) -> str:
        if value is None:
            return "unknown"
        normalized = str(value).strip().lower()
        return _CONDITION_MAP.get(normalized, normalized or "unknown")

    @staticmethod
    def _normalize_listing_status(value: Any) -> str:
        if value is None:
            return "unknown"
        normalized = str(value).strip().lower()
        return _LISTING_STATUS_MAP.get(normalized, "unknown")

    @staticmethod
    def _normalize_auction_type(value: Any) -> str:
        if value is None:
            return "unknown"
        normalized = str(value).strip().lower()
        return _AUCTION_TYPE_MAP.get(normalized, "unknown")

    @staticmethod
    def _availability_from_status(listing_status: str) -> str:
        if listing_status == "active":
            return "in_stock"
        if listing_status == "sold":
            return "sold"
        if listing_status == "ended":
            return "ended"
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
    def validate_payload(payload: dict[str, object]) -> None:
        """
        Validate top-level payload structure.

        Args:
            payload: Response payload.

        Raises:
            YahooAuctionResponseError: When payload structure is invalid.
        """
        if not isinstance(payload, dict):
            raise YahooAuctionResponseError("Yahoo Auction payload must be a JSON object")
        items = payload.get("items")
        if items is not None and not isinstance(items, list):
            raise YahooAuctionResponseError("Yahoo Auction items must be a list when present")
