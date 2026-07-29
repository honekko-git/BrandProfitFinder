"""Non-mutation tests for profit discovery scoring layer."""

from __future__ import annotations

import copy
from decimal import Decimal

from models.marketplace_listing import MarketplaceListing
from models.marketplace_search_result import MarketplaceSearchResult
from models.price_result import PriceResult
from models.product import Product
from price_compare.marketplace_profit_service import calculate_profit_from_search_result
from price_compare.profit_calculator import ProfitCalculator
from profit_intelligence.discovery_engine import DiscoveryEngine, attach_discovery_score_metadata


def _profit_fields(result: PriceResult) -> dict[str, object]:
    return {
        "profit_jpy": result.profit_jpy,
        "profit_margin": result.profit_margin,
        "roi": result.roi,
        "is_profitable": result.is_profitable,
        "total_cost_jpy": result.total_cost_jpy,
        "marketplace_fee_jpy": result.marketplace_fee_jpy,
        "domestic_sale_price_jpy": result.domestic_sale_price_jpy,
    }


def test_discovery_scoring_does_not_modify_profit_fields() -> None:
    result = PriceResult(
        profit_jpy=Decimal("15000"),
        profit_margin=Decimal("28"),
        roi=Decimal("75"),
        calculation_status="success",
        metadata={
            "brand": "gucci",
            "identity_confidence_score": 0.88,
            "sales_last_30_days": 25,
            "listing_count": 2,
        },
    )
    before = _profit_fields(result)
    snapshot = copy.deepcopy(result)

    discovery = DiscoveryEngine().score(result)
    attach_discovery_score_metadata(result, discovery)

    assert _profit_fields(result) == before
    assert result.profit_jpy == snapshot.profit_jpy
    assert result.profit_margin == snapshot.profit_margin
    assert result.roi == snapshot.roi


def test_pipeline_profit_fields_unchanged_after_discovery_scoring() -> None:
    product = Product(name="Bag", brand="Gucci", price=600.0, currency="USD", exchange_rate=150.0)
    listing = MarketplaceListing(
        marketplace_name="rakuten",
        listing_id="shop:1",
        title="Gucci Bag",
        brand="gucci",
        model_number="123",
        sku="123",
        price_jpy=Decimal("128000"),
        shipping_jpy=Decimal("0"),
    )
    search_result = MarketplaceSearchResult(
        product=product,
        marketplace_name="rakuten",
        selected_listing=listing,
        selected_price_jpy=Decimal("128000"),
    )
    calculator = ProfitCalculator()
    enriched = calculate_profit_from_search_result(search_result, calculator)
    before = _profit_fields(enriched)

    discovery = DiscoveryEngine().score(enriched)
    attach_discovery_score_metadata(enriched, discovery)

    assert _profit_fields(enriched) == before
