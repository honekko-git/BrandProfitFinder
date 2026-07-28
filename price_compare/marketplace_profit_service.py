"""
Bridge domestic marketplace search results to profit calculation.
"""

import logging
from decimal import Decimal

from models.marketplace_search_result import MarketplaceSearchResult
from models.price_result import PriceResult
from models.product import Product
from price_compare.profit_calculator import ProfitCalculator

logger = logging.getLogger(__name__)


def calculate_profit_from_search_result(
    search_result: MarketplaceSearchResult,
    calculator: ProfitCalculator,
) -> PriceResult:
    """
    Calculate profit using selected domestic price from a search result.

    Args:
        search_result: Domestic marketplace search outcome.
        calculator: Profit calculator instance.

    Returns:
        PriceResult for the associated product.
    """
    product = search_result.product
    if product is None:
        logger.warning("Marketplace search result has no product")
        return PriceResult(
            calculation_status="invalid_domestic_price",
            error_message="missing product on search result",
            domestic_market=search_result.marketplace_name,
        )

    domestic_price = search_result.selected_price_jpy
    domestic_market = search_result.marketplace_name
    selected_listing = search_result.selected_listing
    if selected_listing is not None:
        domestic_market = selected_listing.marketplace_name or domestic_market

    if domestic_price is None or domestic_price <= 0:
        logger.warning(
            "No valid domestic price for product %r: %s",
            product.name,
            search_result.error_message,
        )
        return calculator.calculate(product, None, domestic_market)

    result = calculator.calculate(product, domestic_price, domestic_market)
    _attach_used_item_metadata(result, selected_listing)
    return result


def calculate_profit_from_search_results(
    search_results: list[MarketplaceSearchResult],
    calculator: ProfitCalculator,
) -> list[PriceResult]:
    """
    Calculate profit for multiple marketplace search results.

    Args:
        search_results: Search outcomes in processing order.
        calculator: Profit calculator instance.

    Returns:
        List of PriceResult instances.
    """
    return [calculate_profit_from_search_result(result, calculator) for result in search_results]


def _attach_used_item_metadata(result: PriceResult, listing) -> None:
    """
    Attach used item auxiliary metadata without changing profit calculation.

    Args:
        result: Calculated price result to enrich.
        listing: Selected marketplace listing, if any.
    """
    if listing is None:
        return

    details = listing.used_item_details
    meta = listing.source_metadata
    adj = details.price_adjustment if details else None
    result.metadata = {
        "source_marketplace": meta.get("source_marketplace") or listing.marketplace_name,
        "source_listing_id": meta.get("source_listing_id") or listing.listing_id,
        "source_currency": meta.get("source_currency") or listing.currency,
        "source_product_id": meta.get("source_product_id") or meta.get("source_stockx_product_id"),
        "source_variant_id": meta.get("source_variant_id") or meta.get("source_stockx_variant_id"),
        "source_designer": meta.get("source_designer"),
        "source_style_code": meta.get("source_style_code") or meta.get("source_stockx_style_code"),
        "source_jan": meta.get("source_jan"),
        "shipping_known": meta.get("source_shipping_known")
        if "source_shipping_known" in meta
        else not listing.shipping_unknown,
        "duties_included": meta.get("source_duties_included"),
        "duties_known": meta.get("source_duties_known"),
        "duties_amount": meta.get("source_duties_amount"),
        "duties_currency": meta.get("source_duties_currency"),
        "duties_applied": False,
        "low_stock": meta.get("source_low_stock"),
        "boutique_type": meta.get("source_boutique_type"),
        "boutique_country": meta.get("source_boutique_country"),
        "boutique_verified": meta.get("source_boutique_verified"),
        "source_season": meta.get("source_season"),
        "source_collection": meta.get("source_collection"),
        "variant_count": meta.get("source_variant_count"),
        "available_variant_count": meta.get("source_available_variant_count"),
        "selected_variant_id": meta.get("source_selected_variant_id"),
        "selected_variant_sku": meta.get("source_selected_variant_sku"),
        "variant_price_applied": False,
        "sale_status": meta.get("source_sale_status"),
        "inventory_status": meta.get("source_inventory_status"),
        "inventory_quantity": meta.get("source_inventory_quantity"),
        "original_price": meta.get("source_original_price"),
        "discount_active": meta.get("source_discount_active"),
        "discount_amount": meta.get("source_discount_amount"),
        "discount_rate": meta.get("source_discount_rate"),
        "previous_price": meta.get("source_previous_price"),
        "discount_applied": False,
        "final_sale": meta.get("source_final_sale"),
        "offer_enabled": meta.get("source_offer_enabled"),
        "minimum_offer": meta.get("source_minimum_offer"),
        "offer_currency": meta.get("source_offer_currency"),
        "offer_applied": False,
        "negotiation_enabled": meta.get("source_negotiation_enabled"),
        "negotiation_currency": meta.get("source_negotiation_currency"),
        "negotiation_applied": False,
        "reference_number": meta.get("source_reference_number"),
        "movement_type": meta.get("source_movement_type"),
        "caliber": meta.get("source_caliber"),
        "case_material": meta.get("source_case_material"),
        "case_diameter_mm": meta.get("source_case_diameter_mm"),
        "bezel_material": meta.get("source_bezel_material"),
        "crystal": meta.get("source_crystal"),
        "dial_color": meta.get("source_dial_color"),
        "bracelet_material": meta.get("source_bracelet_material"),
        "bracelet_color": meta.get("source_bracelet_color"),
        "production_year": meta.get("source_production_year"),
        "water_resistance_m": meta.get("source_water_resistance_m"),
        "power_reserve_hours": meta.get("source_power_reserve_hours"),
        "watch_functions": meta.get("source_watch_functions"),
        "used_condition": details.condition.value if details else None,
        "condition_score": details.condition_score_value if details else None,
        "condition_confidence": details.condition_confidence if details else None,
        "data_completeness": details.data_completeness if details else None,
        "authentication_status": details.authentication.status.value
        if details
        else meta.get("authentication_status"),
        "seller_type": details.seller_details.seller_type.value if details else None,
        "seller_rating": float(details.seller_details.seller_rating)
        if details and details.seller_details.seller_rating is not None
        else None,
        "seller_review_count": details.seller_details.seller_review_count if details else None,
        "seller_transactions": meta.get("source_seller_transactions"),
        "seller_joined_year": meta.get("source_seller_joined_year"),
        "seller_verified": details.seller_details.seller_verified if details else None,
        "seller_trusted": meta.get("source_seller_trusted"),
        "return_accepted": details.return_policy.return_accepted
        if details
        else meta.get("source_return_accepted"),
        "return_period_days": meta.get("source_return_period_days"),
        "risk_level": details.risk_level if details else None,
        "risk_flags": details.risk_flags if details else [],
        "suggested_adjusted_price_jpy": adj.adjusted_price_jpy if adj else None,
        "adjustment_applied": False,
        "used_item_warnings": list(details.warnings) if details else [],
        "source_size": meta.get("source_size"),
        "source_size_system": meta.get("source_size_system"),
        "source_sku": meta.get("source_stockx_sku"),
        "source_release_year": meta.get("source_stockx_release_year"),
        "source_release_date": meta.get("source_stockx_release_date"),
        "price_source": meta.get("source_stockx_price_source"),
        "lowest_ask": meta.get("source_stockx_lowest_ask"),
        "lowest_ask_currency": meta.get("source_stockx_lowest_ask_currency"),
        "lowest_ask_known": meta.get("source_stockx_lowest_ask_known"),
        "highest_bid": meta.get("source_stockx_highest_bid"),
        "highest_bid_currency": meta.get("source_stockx_highest_bid_currency"),
        "highest_bid_known": meta.get("source_stockx_highest_bid_known"),
        "last_sale": meta.get("source_stockx_last_sale"),
        "last_sale_currency": meta.get("source_stockx_last_sale_currency"),
        "last_sale_known": meta.get("source_stockx_last_sale_known"),
        "sales_last_72_hours": meta.get("source_stockx_sales_72h"),
        "sales_last_30_days": meta.get("source_stockx_sales_30d"),
        "asks_count": meta.get("source_stockx_asks_count"),
        "bids_count": meta.get("source_stockx_bids_count"),
        "price_premium_rate": meta.get("source_stockx_premium_rate"),
        "volatility_rate": meta.get("source_stockx_volatility_rate"),
        "fees_known": meta.get("source_stockx_fees_known"),
        "fees_amount": meta.get("source_stockx_fees_amount"),
        "fees_currency": meta.get("source_stockx_fees_currency"),
        "market_price_applied": False,
        "highest_bid_applied": False,
        "last_sale_applied": False,
        "fees_applied": False,
    }
