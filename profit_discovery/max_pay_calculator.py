"""Maximum acceptable purchase price calculator."""

from __future__ import annotations

from decimal import Decimal

from import_cost.context import ImportCostContext
from import_cost.engine import ImportCostEngine
from models.price_result import PriceResult
from price_compare.profit_config import ProfitConfig
from profit_policy.money import round_jpy


class MaxPayCalculator:
    """
    Calculate the maximum acceptable overseas purchase price in JPY.

    Reuses ImportCostEngine and profit policy configuration without duplicating
    ProfitCalculator profit formulas.
    """

    def __init__(
        self,
        *,
        profit_config: ProfitConfig | None = None,
        import_cost_engine: ImportCostEngine | None = None,
    ) -> None:
        self._profit_config = profit_config or ProfitConfig()
        self._import_cost_engine = import_cost_engine or ImportCostEngine()

    def calculate(
        self,
        result: PriceResult,
        target_profit_jpy: Decimal,
    ) -> Decimal | None:
        """
        Return the maximum purchase price in JPY that still meets target profit.

        Uses ImportCostEngine to account for fees, shipping, and import costs.
        """
        if not result.is_valid:
            return None

        domestic_sale = result.domestic_sale_price_jpy
        exchange_rate = result.exchange_rate
        currency = (result.source_currency or "USD").upper()
        if domestic_sale is None or domestic_sale <= 0:
            return None
        if exchange_rate is None or exchange_rate <= 0:
            return None

        marketplace_config = self._profit_config.resolve_marketplace(result.domestic_market or "manual")
        max_source_purchase = self._find_max_source_purchase(
            result=result,
            target_profit_jpy=target_profit_jpy,
            currency=currency,
            exchange_rate=exchange_rate,
            domestic_sale=domestic_sale,
            marketplace_config=marketplace_config,
        )
        if max_source_purchase <= 0:
            return Decimal("0")

        if currency == "JPY":
            return round_jpy(max_source_purchase)
        return round_jpy(max_source_purchase * exchange_rate)

    def _find_max_source_purchase(
        self,
        *,
        result: PriceResult,
        target_profit_jpy: Decimal,
        currency: str,
        exchange_rate: Decimal,
        domestic_sale: Decimal,
        marketplace_config: object,
    ) -> Decimal:
        upper_bound = domestic_sale / exchange_rate if currency != "JPY" else domestic_sale
        if result.source_purchase_price is not None and result.source_purchase_price > upper_bound:
            upper_bound = result.source_purchase_price

        low = Decimal("0")
        high = upper_bound
        best = Decimal("0")

        for _ in range(64):
            if high - low <= Decimal("0.01"):
                break
            mid = (low + high) / Decimal("2")
            profit = self._profit_at_source_purchase(
                source_purchase=mid,
                result=result,
                currency=currency,
                exchange_rate=exchange_rate,
                domestic_sale=domestic_sale,
                marketplace_config=marketplace_config,
            )
            if profit >= target_profit_jpy:
                best = mid
                low = mid
            else:
                high = mid

        return best

    def _profit_at_source_purchase(
        self,
        *,
        source_purchase: Decimal,
        result: PriceResult,
        currency: str,
        exchange_rate: Decimal,
        domestic_sale: Decimal,
        marketplace_config: object,
    ) -> Decimal:
        context = ImportCostContext.create(
            source_purchase=source_purchase,
            currency=currency,
            exchange_rate=exchange_rate,
            domestic_sale_jpy=domestic_sale,
            domestic_market=result.domestic_market or "manual",
            payment_fee_jpy=_optional_cost(result, "payment_fee_jpy"),
            insurance_jpy=_optional_cost(result, "insurance_jpy"),
            packaging_jpy=_optional_cost(result, "packaging_jpy"),
        )
        breakdown = self._import_cost_engine.calculate(context, marketplace_config)
        return domestic_sale - breakdown.total_cost_jpy - breakdown.marketplace_fee_jpy


def _optional_cost(result: PriceResult, key: str) -> Decimal | None:
    value = result.metadata.get(key)
    if value is None:
        return None
    return Decimal(str(value))
