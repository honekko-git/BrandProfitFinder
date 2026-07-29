"""Phase 21: marketplace configuration and profit policy engine."""

from __future__ import annotations

from decimal import Decimal

import pytest

from main import build_phase3_calculator, build_phase3_products, run_comparison_demo
from models.product import Product
from price_compare.profit_calculator import ProfitCalculator
from price_compare.profit_config import ProfitConfig
from profit_policy.currency_policy import CurrencyPolicy, KNOWN_CURRENCIES
from profit_policy.fee_policy import FeePolicy
from profit_policy.marketplace_configuration import MarketplaceConfiguration
from profit_policy.shipping_policy import ShippingPolicy
from profit_policy.tax_policy import TaxPolicy


@pytest.fixture
def base_product() -> Product:
    return Product(
        name="Policy Bag",
        brand="Brand",
        price=100.0,
        original_price=120.0,
        sale_price=100.0,
        currency="USD",
        exchange_rate=100.0,
        store_name="Cettire",
        sku="POLICY-001",
    )


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


def test_marketplace_configuration_from_profit_config(legacy_config: ProfitConfig) -> None:
    config = MarketplaceConfiguration.from_profit_config("rakuten", legacy_config)
    assert config.marketplace_id == "rakuten"
    assert config.fee_policy.fee_rate == Decimal("0.10")
    assert config.shipping_policy.international_shipping_jpy == Decimal("1000")
    assert config.tax_policy.customs_duty_rate == Decimal("0.10")
    assert config.other_costs_jpy == Decimal("200")


def test_profit_config_resolve_marketplace_fallback(legacy_config: ProfitConfig) -> None:
    resolved = legacy_config.resolve_marketplace("manual")
    assert resolved.fee_policy.fee_rate == legacy_config.marketplace_fee_rate
    assert resolved.shipping_policy.domestic_shipping_jpy == legacy_config.domestic_shipping_jpy


def test_marketplace_specific_configuration_override(legacy_config: ProfitConfig) -> None:
    rakuten_config = MarketplaceConfiguration(
        marketplace_id="rakuten",
        fee_policy=FeePolicy(fee_rate=Decimal("0.08")),
        shipping_policy=ShippingPolicy(
            international_shipping_jpy=Decimal("1500"),
            domestic_shipping_jpy=Decimal("600"),
        ),
        tax_policy=TaxPolicy(
            customs_duty_rate=Decimal("0.05"),
            import_tax_rate=Decimal("0.08"),
        ),
        currency_policy=CurrencyPolicy(),
        other_costs_jpy=Decimal("100"),
    )
    legacy_config.marketplace_configurations["rakuten"] = rakuten_config
    resolved = legacy_config.resolve_marketplace("rakuten")
    assert resolved.fee_policy.fee_rate == Decimal("0.08")
    assert resolved.shipping_policy.international_shipping_jpy == Decimal("1500")


def test_fee_policy_compute_fee() -> None:
    policy = FeePolicy(fee_rate=Decimal("0.12"))
    assert policy.compute_fee(Decimal("80000")) == Decimal("9600")


def test_shipping_policy_costs() -> None:
    policy = ShippingPolicy(
        international_shipping_jpy=Decimal("2500"),
        domestic_shipping_jpy=Decimal("800"),
    )
    assert policy.international_cost() == Decimal("2500")
    assert policy.domestic_cost() == Decimal("800")


def test_tax_policy_preserves_existing_formula() -> None:
    policy = TaxPolicy(customs_duty_rate=Decimal("0.10"), import_tax_rate=Decimal("0.10"))
    customs_base = Decimal("11000")
    customs_duty, import_tax = policy.compute_import_charges(customs_base)
    assert customs_duty == Decimal("1100")
    assert import_tax == Decimal("1210")


def test_currency_policy_validation_only(base_product: Product) -> None:
    policy = CurrencyPolicy()
    assert policy.validate_currency("USD") is True
    assert policy.validate_currency("AUD") is False
    assert policy.resolve_exchange_rate(base_product, "USD") == Decimal("100")
    assert policy.resolve_exchange_rate(base_product, "JPY") == Decimal("1")
    assert KNOWN_CURRENCIES == frozenset({"USD", "EUR", "JPY"})


def test_currency_policy_unknown_currency_without_rate(base_product: Product) -> None:
    policy = CurrencyPolicy()
    product = Product(
        name="AUD Item",
        price=100.0,
        currency="AUD",
        exchange_rate=0.0,
    )
    assert policy.resolve_exchange_rate(product, "AUD") is None


def test_profit_calculator_uses_policy_layer(base_product: Product, legacy_config: ProfitConfig) -> None:
    calculator = ProfitCalculator(legacy_config)
    result = calculator.calculate(base_product, Decimal("80000"), domestic_market="manual")
    assert result.marketplace_fee_jpy == Decimal("8000")
    assert result.international_shipping_jpy == Decimal("1000")
    assert result.customs_duty_jpy == Decimal("1100")
    assert result.import_tax_jpy == Decimal("1210")
    assert result.domestic_shipping_jpy == Decimal("500")
    assert result.other_costs_jpy == Decimal("200")


def test_profit_calculator_marketplace_specific_policy(
    base_product: Product,
    legacy_config: ProfitConfig,
) -> None:
    legacy_config.marketplace_configurations["stockx"] = MarketplaceConfiguration(
        marketplace_id="stockx",
        fee_policy=FeePolicy(fee_rate=Decimal("0.15")),
        shipping_policy=ShippingPolicy(
            international_shipping_jpy=Decimal("2000"),
            domestic_shipping_jpy=Decimal("700"),
        ),
        tax_policy=TaxPolicy(
            customs_duty_rate=Decimal("0.08"),
            import_tax_rate=Decimal("0.10"),
        ),
        currency_policy=CurrencyPolicy(),
        other_costs_jpy=Decimal("300"),
    )
    calculator = ProfitCalculator(legacy_config)
    result = calculator.calculate(base_product, Decimal("80000"), domestic_market="stockx")
    assert result.marketplace_fee_jpy == Decimal("12000")
    assert result.international_shipping_jpy == Decimal("2000")
    assert result.other_costs_jpy == Decimal("300")


def test_build_phase3_calculator_parity_with_policy_defaults() -> None:
    calculator = build_phase3_calculator()
    product = build_phase3_products()[0]
    result = calculator.calculate(product, Decimal("50000"), domestic_market="manual")
    config = calculator.config.resolve_marketplace("manual")
    assert result.international_shipping_jpy == config.shipping_policy.international_cost()
    assert result.marketplace_fee_jpy == config.fee_policy.compute_fee(Decimal("50000"))


def test_profit_calculator_input_product_not_modified(
    base_product: Product,
    legacy_config: ProfitConfig,
) -> None:
    original_price = base_product.price
    ProfitCalculator(legacy_config).calculate(base_product, Decimal("80000"))
    assert base_product.price == original_price
