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
        "shipping_known": meta.get("source_shipping_known")
        if "source_shipping_known" in meta
        else not listing.shipping_unknown,
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
        "used_condition": details.condition.value if details else None,
        "condition_score": details.condition_score_value if details else None,
        "condition_confidence": details.condition_confidence if details else None,
        "data_completeness": details.data_completeness if details else None,
        "authentication_status": details.authentication.status.value if details else None,
        "seller_type": details.seller_details.seller_type.value if details else None,
        "seller_rating": float(details.seller_details.seller_rating)
        if details and details.seller_details.seller_rating is not None
        else None,
        "seller_review_count": details.seller_details.seller_review_count if details else None,
        "seller_transactions": meta.get("source_seller_transactions"),
        "seller_joined_year": meta.get("source_seller_joined_year"),
        "seller_verified": details.seller_details.seller_verified if details else None,
        "return_accepted": details.return_policy.return_accepted if details else None,
        "risk_level": details.risk_level if details else None,
        "risk_flags": details.risk_flags if details else [],
        "suggested_adjusted_price_jpy": adj.adjusted_price_jpy if adj else None,
        "adjustment_applied": False,
        "used_item_warnings": list(details.warnings) if details else [],
    }
