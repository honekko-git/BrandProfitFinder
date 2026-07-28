"""
Domestic marketplace listing model.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from models.used_item_details import UsedItemDetails


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
    used_item_details: UsedItemDetails | None = None

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
            **self._used_item_export_fields(),
            **self._source_export_fields(),
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

    def _used_item_export_fields(self) -> dict[str, Any]:
        details = self.used_item_details
        if details is None:
            return {
                "used_condition": None,
                "used_condition_raw": None,
                "condition_score": None,
                "condition_confidence": None,
                "data_completeness": None,
                "accessory_completeness": None,
                "authentication_status": None,
                "authentication_provider": None,
                "seller_type": None,
                "return_accepted": None,
                "return_period_days": None,
                "risk_level": None,
                "risk_flags": None,
                "risk_reasons": None,
                "suggested_adjustment_rate": None,
                "suggested_adjusted_price_jpy": None,
                "adjustment_applied": None,
                "used_item_warnings": None,
            }

        adj = details.price_adjustment
        return {
            "used_condition": details.condition.value,
            "used_condition_raw": details.condition_raw or None,
            "condition_score": details.condition_score_value,
            "condition_confidence": details.condition_confidence,
            "data_completeness": details.data_completeness,
            "accessory_completeness": details.accessory_completeness.value,
            "authentication_status": details.authentication.status.value,
            "authentication_provider": details.authentication.provider or None,
            "seller_type": details.seller_details.seller_type.value,
            "return_accepted": details.return_policy.return_accepted,
            "return_period_days": details.return_policy.return_period_days,
            "risk_level": details.risk_level,
            "risk_flags": ", ".join(details.risk_flags) if details.risk_flags else None,
            "risk_reasons": "; ".join(details.risk_reasons) if details.risk_reasons else None,
            "suggested_adjustment_rate": adj.adjustment_rate if adj else None,
            "suggested_adjusted_price_jpy": adj.adjusted_price_jpy if adj else None,
            "adjustment_applied": adj.applied if adj else False,
            "used_item_warnings": "; ".join(details.warnings) if details.warnings else None,
        }

    def _source_export_fields(self) -> dict[str, Any]:
        meta = self.source_metadata
        return {
            "source_marketplace": meta.get("source_marketplace") or None,
            "source_listing_id": meta.get("source_listing_id") or None,
            "source_currency": meta.get("source_currency") or None,
            "source_shipping_known": meta.get("source_shipping_known"),
            "source_sale_status": meta.get("source_sale_status") or None,
            "source_category": meta.get("source_category") or None,
            "source_sub_category": meta.get("source_sub_category") or None,
            "source_material": meta.get("source_material") or None,
            "source_gender": meta.get("source_gender") or None,
            "source_country": meta.get("source_country") or None,
            "source_listed_at": meta.get("source_listed_at") or None,
            "vestiaire_parse_warnings": meta.get("vestiaire_parse_warnings") or None,
            "source_original_price": meta.get("source_original_price"),
            "source_discount_active": meta.get("source_discount_active"),
            "source_discount_amount": meta.get("source_discount_amount"),
            "source_discount_rate": meta.get("source_discount_rate"),
            "source_previous_price": meta.get("source_previous_price"),
            "source_inventory_status": meta.get("source_inventory_status") or None,
            "source_inventory_quantity": meta.get("source_inventory_quantity"),
            "fashionphile_parse_warnings": meta.get("fashionphile_parse_warnings") or None,
            "source_final_sale": meta.get("source_final_sale"),
            "therealreal_parse_warnings": meta.get("therealreal_parse_warnings") or None,
            "source_offer_enabled": meta.get("source_offer_enabled"),
            "source_minimum_offer": meta.get("source_minimum_offer"),
            "source_offer_currency": meta.get("source_offer_currency") or None,
            "source_seller_transactions": meta.get("source_seller_transactions"),
            "source_seller_joined_year": meta.get("source_seller_joined_year"),
            "grailed_parse_warnings": meta.get("grailed_parse_warnings") or None,
            "source_reference_number": meta.get("source_reference_number") or None,
            "source_movement_type": meta.get("source_movement_type") or None,
            "source_caliber": meta.get("source_caliber") or None,
            "source_case_material": meta.get("source_case_material") or None,
            "source_case_diameter_mm": meta.get("source_case_diameter_mm"),
            "source_bezel_material": meta.get("source_bezel_material") or None,
            "source_crystal": meta.get("source_crystal") or None,
            "source_dial_color": meta.get("source_dial_color") or None,
            "source_bracelet_material": meta.get("source_bracelet_material") or None,
            "source_bracelet_color": meta.get("source_bracelet_color") or None,
            "source_production_year": meta.get("source_production_year"),
            "source_water_resistance_m": meta.get("source_water_resistance_m"),
            "source_power_reserve_hours": meta.get("source_power_reserve_hours"),
            "source_watch_functions": meta.get("source_watch_functions") or None,
            "source_negotiation_enabled": meta.get("source_negotiation_enabled"),
            "source_negotiation_currency": meta.get("source_negotiation_currency") or None,
            "source_seller_trusted": meta.get("source_seller_trusted"),
            "chrono24_parse_warnings": meta.get("chrono24_parse_warnings") or None,
            "source_product_id": meta.get("source_product_id") or None,
            "source_variant_id": meta.get("source_variant_id") or None,
            "source_designer": meta.get("source_designer") or None,
            "source_style_code": meta.get("source_style_code") or None,
            "source_season": meta.get("source_season") or None,
            "source_collection": meta.get("source_collection") or None,
            "source_duties_included": meta.get("source_duties_included"),
            "source_duties_known": meta.get("source_duties_known"),
            "source_duties_amount": meta.get("source_duties_amount"),
            "source_duties_currency": meta.get("source_duties_currency") or None,
            "source_low_stock": meta.get("source_low_stock"),
            "source_boutique_type": meta.get("source_boutique_type") or None,
            "source_boutique_country": meta.get("source_boutique_country") or None,
            "source_boutique_verified": meta.get("source_boutique_verified"),
            "source_variant_count": meta.get("source_variant_count"),
            "source_available_variant_count": meta.get("source_available_variant_count"),
            "source_selected_variant_id": meta.get("source_selected_variant_id") or None,
            "farfetch_parse_warnings": meta.get("farfetch_parse_warnings") or None,
            "source_stockx_product_id": meta.get("source_stockx_product_id") or None,
            "source_stockx_variant_id": meta.get("source_stockx_variant_id") or None,
            "source_stockx_style_code": meta.get("source_stockx_style_code") or None,
            "source_stockx_sku": meta.get("source_stockx_sku") or None,
            "source_stockx_size_system": meta.get("source_stockx_size_system") or None,
            "source_stockx_release_year": meta.get("source_stockx_release_year"),
            "source_stockx_release_date": meta.get("source_stockx_release_date") or None,
            "source_stockx_price_source": meta.get("source_stockx_price_source") or None,
            "source_stockx_lowest_ask": meta.get("source_stockx_lowest_ask"),
            "source_stockx_highest_bid": meta.get("source_stockx_highest_bid"),
            "source_stockx_last_sale": meta.get("source_stockx_last_sale"),
            "source_stockx_sales_72h": meta.get("source_stockx_sales_72h"),
            "source_stockx_sales_30d": meta.get("source_stockx_sales_30d"),
            "source_stockx_asks_count": meta.get("source_stockx_asks_count"),
            "source_stockx_bids_count": meta.get("source_stockx_bids_count"),
            "source_stockx_premium_rate": meta.get("source_stockx_premium_rate"),
            "source_stockx_volatility_rate": meta.get("source_stockx_volatility_rate"),
            "source_stockx_fees_known": meta.get("source_stockx_fees_known"),
            "source_stockx_fees_amount": meta.get("source_stockx_fees_amount"),
            "stockx_parse_warnings": meta.get("stockx_parse_warnings") or None,
            "source_goat_style_code": meta.get("source_goat_style_code") or None,
            "source_goat_sku": meta.get("source_goat_sku") or None,
            "source_goat_size_system": meta.get("source_goat_size_system") or None,
            "source_goat_colorway": meta.get("source_goat_colorway") or None,
            "source_goat_box_condition": meta.get("source_goat_box_condition") or None,
            "source_goat_seller_region": meta.get("source_goat_seller_region") or None,
            "source_goat_release_year": meta.get("source_goat_release_year"),
            "source_goat_condition_normalized": meta.get("source_goat_condition_normalized") or None,
            "source_goat_fees_known": meta.get("source_goat_fees_known"),
            "goat_parse_warnings": meta.get("goat_parse_warnings") or None,
        }
