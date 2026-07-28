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
    if search_result.selected_listing is not None:
        domestic_market = search_result.selected_listing.marketplace_name or domestic_market

    if domestic_price is None or domestic_price <= 0:
        logger.warning(
            "No valid domestic price for product %r: %s",
            product.name,
            search_result.error_message,
        )
        return calculator.calculate(product, None, domestic_market)

    return calculator.calculate(product, domestic_price, domestic_market)


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
