"""Non-mutation tests for profit discovery metadata enrichment."""

from __future__ import annotations

from decimal import Decimal

from models.marketplace_listing import MarketplaceListing
from models.marketplace_search_result import MarketplaceSearchResult
from models.product import Product
from price_compare.marketplace_profit_service import calculate_profit_from_search_result
from price_compare.profit_calculator import ProfitCalculator
from price_compare.profit_config import ProfitConfig


def _profit_snapshot(result) -> dict[str, object]:
    return {
        "profit_jpy": result.profit_jpy,
        "profit_margin": result.profit_margin,
        "roi": result.roi,
        "is_profitable": result.is_profitable,
        "purchase_price_jpy": result.purchase_price_jpy,
        "total_cost_jpy": result.total_cost_jpy,
        "marketplace_fee_jpy": result.marketplace_fee_jpy,
        "domestic_sale_price_jpy": result.domestic_sale_price_jpy,
        "calculation_status": result.calculation_status,
    }


def test_discovery_metadata_enrichment_does_not_change_profit_fields() -> None:
    product = Product(
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
    calculator = ProfitCalculator(
        ProfitConfig(
            international_shipping_jpy=Decimal("1000"),
            customs_duty_rate=Decimal("0.10"),
            import_tax_rate=Decimal("0.10"),
            domestic_shipping_jpy=Decimal("500"),
            marketplace_fee_rate=Decimal("0.10"),
            other_costs_jpy=Decimal("200"),
        )
    )
    baseline = calculator.calculate(product, Decimal("80000"), "manual")
    baseline_snapshot = _profit_snapshot(baseline)

    listing = MarketplaceListing(
        marketplace_name="rakuten",
        listing_id="shop:001",
        title="Calc Bag Domestic",
        brand="Brand",
        model_number="MODEL-1",
        sku="CALC-001",
        jan_code="4901234567890",
        price_jpy=Decimal("80000"),
        shipping_jpy=Decimal("0"),
        source_metadata={"sales_last_30_days": 12},
    )
    search_result = MarketplaceSearchResult(
        product=product,
        marketplace_name="rakuten",
        selected_listing=listing,
        selected_price_jpy=Decimal("80000"),
    )

    enriched = calculate_profit_from_search_result(search_result, calculator)

    assert _profit_snapshot(enriched) == baseline_snapshot
    assert len(enriched.metadata) > 0
    assert enriched.metadata["brand"] == "brand"
    assert enriched.metadata["sku"] == "CALC-001"
    assert "competition_score" in enriched.metadata
    assert "market_signal_confidence_score" in enriched.metadata


def test_metadata_only_grows_relative_to_direct_calculator_result() -> None:
    product = Product(name="Bag", brand="Demo", price=100.0, currency="USD", exchange_rate=150.0)
    calculator = ProfitCalculator()
    direct = calculator.calculate(product, Decimal("50000"), "yahoo")

    listing = MarketplaceListing(
        marketplace_name="yahoo",
        listing_id="Y-100",
        title="Demo Bag",
        brand="Demo",
        price_jpy=Decimal("50000"),
    )
    search_result = MarketplaceSearchResult(
        product=product,
        marketplace_name="yahoo",
        selected_listing=listing,
        selected_price_jpy=Decimal("50000"),
    )
    enriched = calculate_profit_from_search_result(search_result, calculator)

    assert enriched.profit_jpy == direct.profit_jpy
    assert enriched.profit_margin == direct.profit_margin
    assert enriched.roi == direct.roi
    assert enriched.metadata
    assert direct.metadata == {}


def test_missing_listing_keeps_profit_and_empty_metadata() -> None:
    product = Product(name="Bag", brand="Demo", price=100.0, currency="USD", exchange_rate=150.0)
    calculator = ProfitCalculator()
    search_result = MarketplaceSearchResult(
        product=product,
        marketplace_name="yahoo",
        selected_listing=None,
        selected_price_jpy=Decimal("50000"),
    )

    result = calculate_profit_from_search_result(search_result, calculator)
    direct = calculator.calculate(product, Decimal("50000"), "yahoo")

    assert _profit_snapshot(result) == _profit_snapshot(direct)
    assert result.metadata == {}
