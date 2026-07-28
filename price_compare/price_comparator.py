"""
Domestic price comparison helpers.
"""

import logging
import statistics
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.marketplace_listing import MarketplaceListing

logger = logging.getLogger(__name__)


class PriceSelectionStrategy(str, Enum):
    """Strategy for choosing a domestic sale price."""

    HIGHEST = "highest"
    LOWEST = "lowest"
    MEDIAN = "median"
    FIRST_VALID = "first_valid"


class PriceComparator:
    """Select domestic marketplace prices from local candidate values."""

    def select_price(
        self,
        prices: list[Decimal | float | int | None],
        strategy: PriceSelectionStrategy = PriceSelectionStrategy.FIRST_VALID,
    ) -> Decimal | None:
        """
        Select one price from a list of candidates.

        Args:
            prices: Candidate prices.
            strategy: Selection strategy.

        Returns:
            Selected price or None when no valid price exists.
        """
        valid = self.filter_valid_prices(prices)
        if not valid:
            return None

        if strategy == PriceSelectionStrategy.FIRST_VALID:
            return valid[0]
        if strategy == PriceSelectionStrategy.HIGHEST:
            return max(valid)
        if strategy == PriceSelectionStrategy.LOWEST:
            return min(valid)
        if strategy == PriceSelectionStrategy.MEDIAN:
            return Decimal(str(statistics.median([float(price) for price in valid])))

        logger.warning("Unknown price selection strategy: %s", strategy)
        return valid[0]

    def select_from_mapping(
        self,
        candidates: dict[str, Decimal | float | int | None],
        strategy: PriceSelectionStrategy = PriceSelectionStrategy.FIRST_VALID,
    ) -> tuple[str, Decimal] | None:
        """
        Select a marketplace and price from a mapping.

        Args:
            candidates: Marketplace name to price mapping.
            strategy: Selection strategy applied to valid values.

        Returns:
            Tuple of (marketplace, price) or None.
        """
        valid_items = [
            (market, price)
            for market, price in candidates.items()
            if (converted := self._to_decimal(price)) is not None and converted > 0
        ]
        if not valid_items:
            return None

        if strategy == PriceSelectionStrategy.FIRST_VALID:
            market, price = valid_items[0]
            return market, price

        selected_price = self.select_price([price for _, price in valid_items], strategy=strategy)
        if selected_price is None:
            return None

        for market, price in valid_items:
            if self._to_decimal(price) == selected_price:
                return market, selected_price

        return valid_items[0][0], selected_price

    def prices_from_listings(
        self,
        listings: list["MarketplaceListing"],
    ) -> list[Decimal]:
        """
        Extract valid total prices from marketplace listings.

        Args:
            listings: Marketplace listing candidates.

        Returns:
            Valid positive total prices preserving order.
        """
        prices = [
            listing.total_price_jpy or listing.compute_total_price_jpy()
            for listing in listings
            if listing.is_valid
        ]
        return self.filter_valid_prices(prices)

    def select_from_listings(
        self,
        listings: list["MarketplaceListing"],
        strategy: PriceSelectionStrategy = PriceSelectionStrategy.FIRST_VALID,
    ) -> tuple["MarketplaceListing", Decimal] | None:
        """
        Select a listing and price using an existing selection strategy.

        Args:
            listings: Valid marketplace listings.
            strategy: Price selection strategy.

        Returns:
            Tuple of (listing, total_price_jpy) or None.
        """
        valid_listings = [listing for listing in listings if listing.is_valid]
        if not valid_listings:
            return None

        selected_price = self.select_price(
            [
                listing.total_price_jpy or listing.compute_total_price_jpy()
                for listing in valid_listings
            ],
            strategy=strategy,
        )
        if selected_price is None:
            return None

        for listing in valid_listings:
            total = listing.total_price_jpy or listing.compute_total_price_jpy()
            if total == selected_price:
                return listing, selected_price

        return valid_listings[0], selected_price

    def filter_valid_prices(
        self,
        prices: list[Decimal | float | int | None],
    ) -> list[Decimal]:
        """
        Return positive decimal prices from a mixed list.

        Args:
            prices: Candidate prices.

        Returns:
            Valid positive prices preserving order.
        """
        valid: list[Decimal] = []
        for price in prices:
            converted = self._to_decimal(price)
            if converted is None or converted <= 0:
                continue
            valid.append(converted)
        return valid

    @staticmethod
    def _to_decimal(value: Decimal | float | int | None) -> Decimal | None:
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except Exception:
            logger.warning("Invalid price value ignored: %r", value)
            return None
