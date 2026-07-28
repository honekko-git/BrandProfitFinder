"""
Marketplace factory for creating domestic marketplace instances.
"""

from config.constants import (
    MARKETPLACE_LOCAL,
    MARKETPLACE_MERCARI,
    MARKETPLACE_RAKUTEN,
    MARKETPLACE_YAHOO,
)
from marketplace.base_marketplace import BaseMarketplace
from marketplace.local_marketplace import LocalMarketplace
from models.marketplace_listing import MarketplaceListing
from price_compare.price_comparator import PriceSelectionStrategy


def create_marketplace(
    marketplace_name: str,
    listings_by_product_key: dict[str, list[MarketplaceListing]] | None = None,
    selection_strategy: PriceSelectionStrategy = PriceSelectionStrategy.HIGHEST,
) -> BaseMarketplace:
    """
    Create a marketplace instance for the given name.

    Args:
        marketplace_name: Marketplace identifier (case-insensitive).
        listings_by_product_key: Optional injected listings for local marketplace.
        selection_strategy: Price selection strategy for local marketplace.

    Returns:
        Configured marketplace instance.

    Raises:
        ValueError: When marketplace is not supported or not yet implemented.
    """
    normalized = marketplace_name.strip().lower()
    if normalized == MARKETPLACE_LOCAL.lower():
        return LocalMarketplace(
            listings_by_product_key=listings_by_product_key,
            selection_strategy=selection_strategy,
        )

    not_implemented = {
        MARKETPLACE_RAKUTEN.lower(): "Rakuten marketplace is not yet implemented",
        MARKETPLACE_YAHOO.lower(): "Yahoo marketplace is not yet implemented",
        MARKETPLACE_MERCARI.lower(): "Mercari marketplace is not yet implemented",
    }
    if normalized in not_implemented:
        raise ValueError(not_implemented[normalized])

    raise ValueError(f"Unsupported marketplace: {marketplace_name}")


def get_all_marketplaces(
    listings_by_product_key: dict[str, list[MarketplaceListing]] | None = None,
) -> list[BaseMarketplace]:
    """
    Return marketplace instances for all implemented marketplaces.

    Args:
        listings_by_product_key: Optional injected listings for local marketplace.

    Returns:
        List of marketplace instances.
    """
    return [create_marketplace(MARKETPLACE_LOCAL, listings_by_product_key=listings_by_product_key)]
