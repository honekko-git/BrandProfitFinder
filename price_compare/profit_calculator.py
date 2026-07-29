"""
Profit calculation engine.
"""

import logging
from decimal import Decimal

from import_cost.context import ImportCostContext
from import_cost.engine import ImportCostEngine
from models.price_result import (
    CALCULATION_ERROR,
    CALCULATION_INVALID_DOMESTIC_PRICE,
    CALCULATION_INVALID_PRICE,
    CALCULATION_INVALID_RATE,
    CALCULATION_SUCCESS,
    CALCULATION_UNKNOWN_CURRENCY,
    PriceResult,
)
from models.product import Product
from price_compare.profit_config import ProfitConfig

logger = logging.getLogger(__name__)


class ProfitCalculator:
    """Calculate profit metrics from overseas products and domestic sale prices."""

    def __init__(
        self,
        config: ProfitConfig | None = None,
        import_cost_engine: ImportCostEngine | None = None,
    ) -> None:
        """
        Initialize calculator with optional fee configuration.

        Args:
            config: Profit calculation settings.
            import_cost_engine: Optional import cost engine override.
        """
        self.config = config or ProfitConfig()
        self._import_cost_engine = import_cost_engine or ImportCostEngine()

    def calculate(
        self,
        product: Product,
        domestic_sale_price_jpy: Decimal | float | int | None,
        domestic_market: str = "manual",
    ) -> PriceResult:
        """
        Calculate profit for a single product.

        Args:
            product: Overseas product. Not modified.
            domestic_sale_price_jpy: Expected domestic sale price in JPY.
            domestic_market: Marketplace label for the domestic price.

        Returns:
            PriceResult with calculation details.
        """
        try:
            return self._calculate_product(product, domestic_sale_price_jpy, domestic_market)
        except Exception as exc:
            logger.exception("Profit calculation failed for product %r", product.name)
            return self._error_result(
                product,
                domestic_market,
                CALCULATION_ERROR,
                str(exc),
            )

    def calculate_many(
        self,
        products: list[Product],
        domestic_prices: dict[str, Decimal | float | int | None] | None = None,
        domestic_market: str = "manual",
    ) -> list[PriceResult]:
        """
        Calculate profit for multiple products.

        Args:
            products: Products to evaluate.
            domestic_prices: Optional SKU-to-price mapping override.
            domestic_market: Default domestic marketplace label.

        Returns:
            List of PriceResult instances in input order.
        """
        price_map = domestic_prices or {}
        results: list[PriceResult] = []
        for product in products:
            override = price_map.get(product.sku)
            domestic_price = override if override is not None else self._default_domestic_price(product)
            results.append(self.calculate(product, domestic_price, domestic_market))
        return results

    def _calculate_product(
        self,
        product: Product,
        domestic_sale_price_jpy: Decimal | float | int | None,
        domestic_market: str,
    ) -> PriceResult:
        marketplace_config = self.config.resolve_marketplace(domestic_market)
        currency_policy = marketplace_config.currency_policy

        source_original = _to_decimal(product.original_price)
        source_sale = _to_decimal(product.sale_price)
        source_purchase = _resolve_purchase_price(source_sale, source_original, _to_decimal(product.price))

        if source_purchase is None or source_purchase <= 0:
            return self._error_result(
                product,
                domestic_market,
                CALCULATION_INVALID_PRICE,
                "source purchase price must be greater than zero",
                source_original=source_original,
                source_sale=source_sale,
            )

        currency = currency_policy.normalize_currency(product.currency or "USD")
        exchange_rate = currency_policy.resolve_exchange_rate(product, currency)
        if exchange_rate is None or exchange_rate <= 0:
            return self._error_result(
                product,
                domestic_market,
                CALCULATION_INVALID_RATE
                if exchange_rate is not None
                else CALCULATION_UNKNOWN_CURRENCY,
                "exchange rate must be greater than zero",
                source_original=source_original,
                source_sale=source_sale,
                source_purchase=source_purchase,
                currency=currency,
            )

        domestic_sale = _to_decimal(domestic_sale_price_jpy)
        if domestic_sale is None or domestic_sale <= 0:
            return self._error_result(
                product,
                domestic_market,
                CALCULATION_INVALID_DOMESTIC_PRICE,
                "domestic sale price must be greater than zero",
                source_original=source_original,
                source_sale=source_sale,
                source_purchase=source_purchase,
                currency=currency,
                exchange_rate=exchange_rate,
            )

        cost_context = ImportCostContext.create(
            source_purchase=source_purchase,
            currency=currency,
            exchange_rate=exchange_rate,
            domestic_sale_jpy=domestic_sale,
            domestic_market=domestic_market,
        )
        costs = self._import_cost_engine.calculate(cost_context, marketplace_config)
        profit = domestic_sale - costs.total_cost_jpy - costs.marketplace_fee_jpy
        profit_margin = _safe_percentage(profit, domestic_sale)
        roi = _safe_percentage(profit, costs.total_cost_jpy)

        return PriceResult(
            product=product,
            source_store=product.store_name,
            source_currency=currency,
            source_original_price=source_original,
            source_sale_price=source_sale,
            source_purchase_price=source_purchase,
            exchange_rate=exchange_rate,
            purchase_price_jpy=costs.purchase_cost_jpy,
            international_shipping_jpy=costs.international_shipping_jpy,
            customs_duty_jpy=costs.customs_duty_jpy,
            import_tax_jpy=costs.import_tax_jpy,
            domestic_shipping_jpy=costs.domestic_shipping_jpy,
            marketplace_fee_jpy=costs.marketplace_fee_jpy,
            other_costs_jpy=costs.reported_other_costs_jpy,
            total_cost_jpy=costs.total_cost_jpy,
            domestic_market=domestic_market,
            domestic_sale_price_jpy=domestic_sale,
            profit_jpy=profit,
            profit_margin=profit_margin,
            roi=roi,
            is_profitable=profit > 0,
            calculation_status=CALCULATION_SUCCESS,
        )

    @staticmethod
    def _default_domestic_price(product: Product) -> Decimal | None:
        best = product.best_japanese_price()
        return _to_decimal(best) if best is not None else None

    def _error_result(
        self,
        product: Product,
        domestic_market: str,
        status: str,
        message: str,
        source_original: Decimal | None = None,
        source_sale: Decimal | None = None,
        source_purchase: Decimal | None = None,
        currency: str = "",
        exchange_rate: Decimal | None = None,
    ) -> PriceResult:
        logger.warning(
            "Invalid profit calculation for %r: %s",
            product.name,
            message,
        )
        return PriceResult(
            product=product,
            source_store=product.store_name,
            source_currency=currency or product.currency.upper(),
            source_original_price=source_original,
            source_sale_price=source_sale,
            source_purchase_price=source_purchase,
            exchange_rate=exchange_rate,
            domestic_market=domestic_market,
            calculation_status=status,
            error_message=message,
            is_profitable=False,
        )


def _resolve_purchase_price(
    sale_price: Decimal | None,
    original_price: Decimal | None,
    fallback_price: Decimal | None,
) -> Decimal | None:
    if sale_price is not None and sale_price > 0:
        return sale_price
    if original_price is not None and original_price > 0:
        return original_price
    if fallback_price is not None and fallback_price > 0:
        return fallback_price
    return None


def _to_decimal(value: Decimal | float | int | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _safe_percentage(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator <= 0:
        return Decimal("0")
    return (numerator / denominator * Decimal("100")).quantize(Decimal("0.01"))
