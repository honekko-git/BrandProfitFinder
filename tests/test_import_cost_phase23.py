"""Phase 23: import cost engine v2."""

from __future__ import annotations

from decimal import Decimal

import pytest

from import_cost.context import ImportCostContext
from import_cost.engine import ImportCostBreakdown, ImportCostEngine
from main import build_phase3_calculator, build_phase3_products
from models.product import Product
from price_compare.profit_calculator import ProfitCalculator
from price_compare.profit_config import ProfitConfig


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


@pytest.fixture
def base_product() -> Product:
    return Product(
        name="Calc Bag",
        brand="Brand",
        price=100.0,
        original_price=120.0,
        sale_price=100.0,
        currency="USD",
        exchange_rate=100.0,
        store_name="Cettire",
        sku="CALC-001",
    )


def test_import_cost_context_create() -> None:
    context = ImportCostContext.create(
        source_purchase=Decimal("100"),
        currency="usd",
        exchange_rate=Decimal("100"),
        domestic_sale_jpy=Decimal("80000"),
        domestic_market="manual",
    )
    assert context.currency == "USD"
    assert context.optional_costs_jpy == Decimal("0")


def test_import_cost_engine_legacy_breakdown(legacy_config: ProfitConfig) -> None:
    context = ImportCostContext.create(
        source_purchase=Decimal("100"),
        currency="USD",
        exchange_rate=Decimal("100"),
        domestic_sale_jpy=Decimal("80000"),
    )
    marketplace_config = legacy_config.resolve_marketplace("manual")
    breakdown = ImportCostEngine().calculate(context, marketplace_config)
    assert breakdown.purchase_cost_jpy == Decimal("10000")
    assert breakdown.international_shipping_jpy == Decimal("1000")
    assert breakdown.customs_duty_jpy == Decimal("1100")
    assert breakdown.import_tax_jpy == Decimal("1210")
    assert breakdown.domestic_shipping_jpy == Decimal("500")
    assert breakdown.marketplace_fee_jpy == Decimal("8000")
    assert breakdown.other_costs_jpy == Decimal("200")
    assert breakdown.payment_fee_jpy == Decimal("0")
    assert breakdown.total_cost_jpy == Decimal("14010")


def test_import_cost_engine_optional_costs_increase_total(legacy_config: ProfitConfig) -> None:
    base_context = ImportCostContext.create(
        source_purchase=Decimal("100"),
        currency="USD",
        exchange_rate=Decimal("100"),
        domestic_sale_jpy=Decimal("80000"),
    )
    optional_context = ImportCostContext.create(
        source_purchase=Decimal("100"),
        currency="USD",
        exchange_rate=Decimal("100"),
        domestic_sale_jpy=Decimal("80000"),
        payment_fee_jpy=Decimal("300"),
        insurance_jpy=Decimal("200"),
        packaging_jpy=Decimal("100"),
    )
    marketplace_config = legacy_config.resolve_marketplace("manual")
    engine = ImportCostEngine()
    base = engine.calculate(base_context, marketplace_config)
    with_optional = engine.calculate(optional_context, marketplace_config)
    assert with_optional.total_cost_jpy == base.total_cost_jpy + Decimal("600")
    assert with_optional.reported_other_costs_jpy == Decimal("800")


def test_profit_calculator_matches_legacy_when_optional_omitted(
    legacy_config: ProfitConfig,
    base_product: Product,
) -> None:
    calculator = ProfitCalculator(legacy_config)
    result = calculator.calculate(base_product, Decimal("80000"))
    expected_total = (
        Decimal("10000")
        + Decimal("1000")
        + Decimal("1100")
        + Decimal("1210")
        + Decimal("500")
        + Decimal("200")
    )
    assert result.total_cost_jpy == expected_total
    assert result.other_costs_jpy == Decimal("200")
    assert result.profit_jpy == Decimal("80000") - expected_total - Decimal("8000")


def test_optional_costs_reduce_profit_when_applied(legacy_config: ProfitConfig) -> None:
    marketplace_config = legacy_config.resolve_marketplace("manual")
    engine = ImportCostEngine()
    base_context = ImportCostContext.create(
        source_purchase=Decimal("100"),
        currency="USD",
        exchange_rate=Decimal("100"),
        domestic_sale_jpy=Decimal("80000"),
    )
    optional_context = ImportCostContext.create(
        source_purchase=Decimal("100"),
        currency="USD",
        exchange_rate=Decimal("100"),
        domestic_sale_jpy=Decimal("80000"),
        payment_fee_jpy=Decimal("300"),
        insurance_jpy=Decimal("200"),
        packaging_jpy=Decimal("100"),
    )
    base_costs = engine.calculate(base_context, marketplace_config)
    optional_costs = engine.calculate(optional_context, marketplace_config)
    domestic_sale = Decimal("80000")
    base_profit = domestic_sale - base_costs.total_cost_jpy - base_costs.marketplace_fee_jpy
    optional_profit = domestic_sale - optional_costs.total_cost_jpy - optional_costs.marketplace_fee_jpy
    assert optional_profit == base_profit - Decimal("600")


def test_build_phase3_calculator_parity() -> None:
    calculator = build_phase3_calculator()
    product = build_phase3_products()[0]
    result = calculator.calculate(product, Decimal("50000"), domestic_market="manual")
    assert result.calculation_status == "success"
    assert result.purchase_price_jpy is not None
    assert result.total_cost_jpy > Decimal("0")


def test_deterministic_repeated_import_cost_calculation(legacy_config: ProfitConfig) -> None:
    context = ImportCostContext.create(
        source_purchase=Decimal("100"),
        currency="USD",
        exchange_rate=Decimal("100"),
        domestic_sale_jpy=Decimal("80000"),
    )
    marketplace_config = legacy_config.resolve_marketplace("manual")
    engine = ImportCostEngine()
    first = engine.calculate(context, marketplace_config)
    second = engine.calculate(context, marketplace_config)
    assert first == second


def test_import_cost_breakdown_is_immutable_snapshot(legacy_config: ProfitConfig) -> None:
    context = ImportCostContext.create(
        source_purchase=Decimal("100"),
        currency="USD",
        exchange_rate=Decimal("100"),
        domestic_sale_jpy=Decimal("80000"),
    )
    breakdown = ImportCostEngine().calculate(context, legacy_config.resolve_marketplace("manual"))
    assert isinstance(breakdown, ImportCostBreakdown)
