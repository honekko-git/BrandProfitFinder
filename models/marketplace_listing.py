"""
Domestic marketplace listing model.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass
class MarketplaceListing:
    """One domestic marketplace listing candidate."""

    marketplace_name: str = ""
    listing_id: str = ""
    title: str = ""
    brand: str = ""
    model_number: str = ""
    sku: str = ""
    jan_code: str = ""
    condition: str = ""
    price_jpy: Decimal = Decimal("0")
    shipping_jpy: Decimal | None = None
    total_price_jpy: Decimal | None = None
    seller_name: str = ""
    seller_rating: Decimal | None = None
    listing_url: str = ""
    image_url: str = ""
    availability: str = ""
    sold_count: int | None = None
    source_query: str = ""
    matched_product_id: str = ""
    match_score: Decimal = Decimal("0")
    is_valid: bool = True
    validation_error: str = ""
    currency: str = "JPY"
    points_jpy: Decimal | None = None
    is_prime: bool = False
    is_amazon_seller: bool = False
    shipping_unknown: bool = False
    point_rate: Decimal | None = None
    source_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.marketplace_name = self.marketplace_name.strip()
        if self.total_price_jpy is None:
            self.total_price_jpy = self.compute_total_price_jpy()

    def compute_total_price_jpy(self) -> Decimal:
        """
        Compute total price from item price and shipping.

        Returns:
            Total price in JPY. Unknown shipping adds no shipping amount.
        """
        if self.shipping_jpy is None or self.shipping_unknown:
            return self.price_jpy
        return self.price_jpy + self.shipping_jpy

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize listing to a flat dictionary for Excel export.

        Returns:
            Export-safe dictionary.
        """
        return {
            "marketplace_name": self.marketplace_name,
            "listing_id": self.listing_id,
            "title": self.title,
            "brand": self.brand,
            "model_number": self.model_number,
            "sku": self.sku,
            "jan_code": self.jan_code,
            "condition": self.condition,
            "price_jpy": float(self.price_jpy),
            "shipping_jpy": float(self.shipping_jpy) if self.shipping_jpy is not None else None,
            "total_price_jpy": float(self.total_price_jpy or self.compute_total_price_jpy()),
            "seller_name": self.seller_name,
            "seller_rating": float(self.seller_rating) if self.seller_rating is not None else None,
            "listing_url": self.listing_url,
            "image_url": self.image_url,
            "availability": self.availability,
            "sold_count": self.sold_count,
            "source_query": self.source_query,
            "matched_product_id": self.matched_product_id,
            "match_score": float(self.match_score),
            "is_valid": self.is_valid,
            "validation_error": self.validation_error,
            "currency": self.currency,
            "points_jpy": float(self.points_jpy) if self.points_jpy is not None else None,
            "is_prime": self.is_prime,
            "is_amazon_seller": self.is_amazon_seller,
            "shipping_unknown": self.shipping_unknown,
            "point_rate": float(self.point_rate) if self.point_rate is not None else None,
            **self._auction_export_fields(),
        }

    def _auction_export_fields(self) -> dict[str, Any]:
        meta = self.source_metadata

        def _float(key: str) -> float | None:
            value = meta.get(key)
            if value is None:
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        def _int(key: str) -> int | None:
            value = meta.get(key)
            if value is None:
                return None
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        return {
            "current_price_jpy": _float("current_price_jpy"),
            "buy_now_price_jpy": _float("buy_now_price_jpy"),
            "winning_price_jpy": _float("winning_price_jpy"),
            "price_source": meta.get("price_source") or None,
            "listing_status": meta.get("listing_status") or None,
            "auction_type": meta.get("auction_type") or None,
            "bid_count": _int("bid_count"),
            "watch_count": _int("watch_count"),
            "start_time": meta.get("start_time") or None,
            "end_time": meta.get("end_time") or None,
        }
