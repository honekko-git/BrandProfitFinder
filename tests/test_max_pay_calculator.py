"""Tests for maximum purchase price calculator."""

from __future__ import annotations

from decimal import Decimal

import pytest

from import_cost.engine import ImportCostEngine
from models.price_result import PriceResult
from price_compare.profit_config import ProfitConfig
from profit_discovery.max_pay_calculator import MaxPayCalculator


@pytest.fixture
def legacy_config() -> ProfitConfig:
    return ProfitConfig(
        international_shipping_jpy=Decimal("1000"),
        customs_duty_rate=Decimal("0.10"),
        import_tax_rate=Decimal("0.10"),
        domestic_shipping_jpy=Decimal("500"),
        marketplace_fee_rate=Decimal("0.10"),
        other_costs_jpy=Decimal("200"),
    )


def test_max_purchase_price_accounts_for_fees_and_import_costs(legacy_config: ProfitConfig) -> None:
    result = PriceResult(
        profit_jpy=Decimal("57990"),
        domestic_sale_price_jpy=Decimal("80000"),
        purchase_price_jpy=Decimal("10000"),
        international_shipping_jpy=Decimal("1000"),
        customs_duty_jpy=Decimal("1100"),
        import_tax_jpy=Decimal("1210"),
        domestic_shipping_jpy=Decimal("500"),
        marketplace_fee_jpy=Decimal("8000"),
        other_costs_jpy=Decimal("200"),
        total_cost_jpy=Decimal("14010"),
        source_currency="USD",
        exchange_rate=Decimal("100"),
        source_purchase_price=Decimal("100"),
        domestic_market="manual",
        calculation_status="success",
    )
    calculator = MaxPayCalculator(profit_config=legacy_config, import_cost_engine=ImportCostEngine())

    max_price = calculator.calculate(result, Decimal("57990"))

    assert max_price is not None
    assert max_price == Decimal("10000")


def test_max_purchase_price_decreases_when_target_profit_increases(legacy_config: ProfitConfig) -> None:
    result = PriceResult(
        profit_jpy=Decimal("57990"),
        domestic_sale_price_jpy=Decimal("80000"),
        purchase_price_jpy=Decimal("10000"),
        total_cost_jpy=Decimal("14010"),
        marketplace_fee_jpy=Decimal("8000"),
        source_currency="USD",
        exchange_rate=Decimal("100"),
        source_purchase_price=Decimal("100"),
        domestic_market="manual",
        calculation_status="success",
    )
    calculator = MaxPayCalculator(profit_config=legacy_config, import_cost_engine=ImportCostEngine())

    lower_target = calculator.calculate(result, Decimal("30000"))
    higher_target = calculator.calculate(result, Decimal("50000"))

    assert lower_target is not None
    assert higher_target is not None
    assert lower_target > higher_target


def test_max_purchase_price_includes_shipping_components(legacy_config: ProfitConfig) -> None:
    result = PriceResult(
        profit_jpy=Decimal("20000"),
        domestic_sale_price_jpy=Decimal("80000"),
        purchase_price_jpy=Decimal("10000"),
        international_shipping_jpy=Decimal("1000"),
        domestic_shipping_jpy=Decimal("500"),
        total_cost_jpy=Decimal("14010"),
        marketplace_fee_jpy=Decimal("8000"),
        source_currency="USD",
        exchange_rate=Decimal("100"),
        source_purchase_price=Decimal("100"),
        domestic_market="manual",
        calculation_status="success",
    )
    calculator = MaxPayCalculator(profit_config=legacy_config, import_cost_engine=ImportCostEngine())

    max_price = calculator.calculate(result, Decimal("20000"))

    assert max_price is not None
    assert max_price < result.domestic_sale_price_jpy


def test_max_purchase_price_returns_none_for_invalid_result() -> None:
    result = PriceResult(calculation_status="invalid_price")

    max_price = MaxPayCalculator().calculate(result, Decimal("5000"))

    assert max_price is None
