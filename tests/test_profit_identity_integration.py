"""Integration tests for product identity in the profit pipeline."""

from __future__ import annotations

from decimal import Decimal

from models.marketplace_listing import MarketplaceListing
from models.marketplace_search_result import MarketplaceSearchResult
from models.product import Product
from price_compare.marketplace_profit_service import calculate_profit_from_search_result
from price_compare.profit_calculator import ProfitCalculator
from price_compare.profit_config import ProfitConfig


def _calculator() -> ProfitCalculator:
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


def _product() -> Product:
    return Product(
        name="Gucci Marmont Wallet",
        brand="GUCCI",
        model="456126",
        sku="456126",
        price=600.0,
        currency="USD",
        exchange_rate=150.0,
    )


def test_product_identity_metadata_attached_to_price_result() -> None:
    listing = MarketplaceListing(
        marketplace_name="rakuten",
        listing_id="shop:123456",
        title="GUCCI GG Marmont Wallet Black",
        brand="GUCCI",
        model_number="456126",
        sku="456126",
        jan_code="4901234567890",
        price_jpy=Decimal("128000"),
        shipping_jpy=Decimal("0"),
        match_score=Decimal("0.95"),
    )
    search_result = MarketplaceSearchResult(
        product=_product(),
        marketplace_name="rakuten",
        selected_listing=listing,
        selected_price_jpy=Decimal("128000"),
    )

    result = calculate_profit_from_search_result(search_result, _calculator())

    assert result.metadata["brand"] == "gucci"
    assert result.metadata["model_number"] == "456126"
    assert result.metadata["jan_code"] == "4901234567890"
    assert result.metadata["sku"] == "456126"
    assert isinstance(result.metadata["identity_confidence_score"], float)
    assert result.metadata["identity_confidence_score"] >= 0.95


def test_missing_identity_fields_do_not_fail_profit_calculation() -> None:
    listing = MarketplaceListing(
        marketplace_name="yahoo",
        listing_id="Y-1",
        title="Unknown Item",
        price_jpy=Decimal("10000"),
        shipping_jpy=Decimal("0"),
    )
    search_result = MarketplaceSearchResult(
        product=_product(),
        marketplace_name="yahoo",
        selected_listing=listing,
        selected_price_jpy=Decimal("10000"),
    )

    result = calculate_profit_from_search_result(search_result, _calculator())

    assert result.is_valid
    assert result.metadata["brand"] == ""
    assert result.metadata["model_number"] == ""
    assert result.metadata["jan_code"] == ""
    assert result.metadata["sku"] == ""
    assert result.metadata["identity_confidence_score"] == 0.0


def test_profit_values_unchanged_when_identity_metadata_attached() -> None:
    listing = MarketplaceListing(
        marketplace_name="amazon_jp",
        listing_id="B0TEST1234",
        title="GUCCI Wallet",
        brand="GUCCI",
        model_number="456126",
        sku="456126",
        price_jpy=Decimal("128000"),
        shipping_jpy=Decimal("0"),
    )
    search_result = MarketplaceSearchResult(
        product=_product(),
        marketplace_name="amazon_jp",
        selected_listing=listing,
        selected_price_jpy=Decimal("128000"),
    )
    calculator = _calculator()
    baseline = calculator.calculate(_product(), Decimal("128000"), "amazon_jp")

    enriched = calculate_profit_from_search_result(search_result, calculator)

    assert enriched.profit_jpy == baseline.profit_jpy
    assert enriched.profit_margin == baseline.profit_margin
    assert enriched.roi == baseline.roi
    assert enriched.is_profitable == baseline.is_profitable
    assert enriched.total_cost_jpy == baseline.total_cost_jpy
    assert enriched.marketplace_fee_jpy == baseline.marketplace_fee_jpy
    assert "identity_confidence_score" in enriched.metadata
