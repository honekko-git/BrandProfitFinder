"""Unit tests for price_compare.profit_calculator."""

from decimal import Decimal

import pytest

from models.price_result import (
    CALCULATION_INVALID_DOMESTIC_PRICE,
    CALCULATION_INVALID_PRICE,
    CALCULATION_INVALID_RATE,
    CALCULATION_SUCCESS,
    CALCULATION_UNKNOWN_CURRENCY,
    PriceResult,
)
from models.product import Product
from price_compare.profit_calculator import ProfitCalculator
from price_compare.profit_config import ProfitConfig


@pytest.fixture
def calculator() -> ProfitCalculator:
    return ProfitCalculator(
        ProfitConfig(
            international_shipping_jpy=Decimal("1000"),
            customs_duty_rate=Decimal("0.10"),
            import_tax_rate=Decimal("0.10"),
            domestic_shipping_jpy=Decimal("500"),
            marketplace_fee_rate=Decimal("0.10"),
            other_costs_jpy=Decimal("200"),
        )
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


def test_prefers_sale_price(calculator: ProfitCalculator, base_product: Product) -> None:
    result = calculator.calculate(base_product, Decimal("80000"))
    assert result.source_purchase_price == Decimal("100")
    assert isinstance(result, PriceResult)


def test_uses_original_price_when_no_sale(calculator: ProfitCalculator) -> None:
    product = Product(
        name="Regular",
        price=90.0,
        original_price=120.0,
        currency="USD",
        exchange_rate=100.0,
    )
    result = calculator.calculate(product, Decimal("70000"))
    assert result.source_purchase_price == Decimal("120")


def test_uses_existing_price_when_no_sale_or_original(calculator: ProfitCalculator) -> None:
    product = Product(name="Fallback", price=80.0, currency="USD", exchange_rate=100.0)
    result = calculator.calculate(product, Decimal("70000"))
    assert result.source_purchase_price == Decimal("80")


def test_exchange_conversion(calculator: ProfitCalculator, base_product: Product) -> None:
    result = calculator.calculate(base_product, Decimal("80000"))
    assert result.purchase_price_jpy == Decimal("10000")


def test_international_shipping_added(calculator: ProfitCalculator, base_product: Product) -> None:
    result = calculator.calculate(base_product, Decimal("80000"))
    assert result.international_shipping_jpy == Decimal("1000")


def test_customs_duty_calculation(calculator: ProfitCalculator, base_product: Product) -> None:
    result = calculator.calculate(base_product, Decimal("80000"))
    assert result.customs_duty_jpy == Decimal("1100")


def test_import_tax_calculation(calculator: ProfitCalculator, base_product: Product) -> None:
    result = calculator.calculate(base_product, Decimal("80000"))
    assert result.import_tax_jpy == Decimal("1210")


def test_domestic_shipping_added(calculator: ProfitCalculator, base_product: Product) -> None:
    result = calculator.calculate(base_product, Decimal("80000"))
    assert result.domestic_shipping_jpy == Decimal("500")


def test_marketplace_fee_calculation(calculator: ProfitCalculator, base_product: Product) -> None:
    result = calculator.calculate(base_product, Decimal("80000"))
    assert result.marketplace_fee_jpy == Decimal("8000")


def test_other_costs_added(calculator: ProfitCalculator, base_product: Product) -> None:
    result = calculator.calculate(base_product, Decimal("80000"))
    assert result.other_costs_jpy == Decimal("200")


def test_profit_amount(calculator: ProfitCalculator, base_product: Product) -> None:
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
    assert result.profit_jpy == Decimal("80000") - expected_total - Decimal("8000")


def test_profit_margin(calculator: ProfitCalculator, base_product: Product) -> None:
    result = calculator.calculate(base_product, Decimal("80000"))
    assert result.profit_margin == (result.profit_jpy / Decimal("80000") * Decimal("100")).quantize(
        Decimal("0.01")
    )


def test_roi(calculator: ProfitCalculator, base_product: Product) -> None:
    result = calculator.calculate(base_product, Decimal("80000"))
    assert result.roi == (result.profit_jpy / result.total_cost_jpy * Decimal("100")).quantize(
        Decimal("0.01")
    )


def test_profitable_result(calculator: ProfitCalculator, base_product: Product) -> None:
    result = calculator.calculate(base_product, Decimal("80000"))
    assert result.is_profitable is True


def test_loss_result(calculator: ProfitCalculator, base_product: Product) -> None:
    result = calculator.calculate(base_product, Decimal("10000"))
    assert result.is_profitable is False


def test_zero_price_is_invalid(calculator: ProfitCalculator) -> None:
    product = Product(name="Zero", price=0.0, currency="USD", exchange_rate=100.0)
    result = calculator.calculate(product, Decimal("50000"))
    assert result.calculation_status == CALCULATION_INVALID_PRICE


def test_negative_price_is_invalid(calculator: ProfitCalculator) -> None:
    product = Product(name="Negative", price=-10.0, currency="USD", exchange_rate=100.0)
    result = calculator.calculate(product, Decimal("50000"))
    assert result.calculation_status == CALCULATION_INVALID_PRICE


def test_zero_exchange_rate_is_invalid(calculator: ProfitCalculator) -> None:
    product = Product(name="Rate", price=100.0, currency="USD", exchange_rate=0.0)
    config = ProfitConfig(exchange_rates={"USD": Decimal("0")})
    calc = ProfitCalculator(config)
    result = calc.calculate(product, Decimal("50000"))
    assert result.calculation_status == CALCULATION_INVALID_RATE


def test_unknown_currency_requires_explicit_rate(calculator: ProfitCalculator) -> None:
    product = Product(name="Unknown", price=100.0, currency="AUD", exchange_rate=0.0)
    result = calculator.calculate(product, Decimal("50000"))
    assert result.calculation_status == CALCULATION_UNKNOWN_CURRENCY


def test_batch_continues_after_invalid(calculator: ProfitCalculator) -> None:
    products = [
        Product(name="Bad", price=0.0, currency="USD", exchange_rate=100.0),
        Product(name="Good", price=100.0, currency="USD", exchange_rate=100.0, sku="GOOD"),
    ]
    results = calculator.calculate_many(products, domestic_prices={"GOOD": Decimal("80000")})
    assert len(results) == 2
    assert results[0].calculation_status == CALCULATION_INVALID_PRICE
    assert results[1].calculation_status == CALCULATION_SUCCESS


def test_input_product_not_modified(calculator: ProfitCalculator, base_product: Product) -> None:
    original_price = base_product.price
    calculator.calculate(base_product, Decimal("80000"))
    assert base_product.price == original_price


def test_returns_price_result_instance(calculator: ProfitCalculator, base_product: Product) -> None:
    result = calculator.calculate(base_product, Decimal("80000"))
    assert isinstance(result, PriceResult)
    assert result.calculation_status == CALCULATION_SUCCESS


def test_invalid_domestic_price(calculator: ProfitCalculator, base_product: Product) -> None:
    result = calculator.calculate(base_product, Decimal("0"))
    assert result.calculation_status == CALCULATION_INVALID_DOMESTIC_PRICE
