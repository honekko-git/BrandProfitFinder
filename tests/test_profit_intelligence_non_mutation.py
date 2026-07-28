"""Deep non-mutation tests for Profit Intelligence scoring."""

from __future__ import annotations

import copy
from decimal import Decimal

from models.marketplace_listing import MarketplaceListing
from models.marketplace_search_result import MarketplaceSearchResult
from models.price_result import PriceResult
from models.product import Product
from price_compare.profit_calculator import ProfitCalculator
from profit_intelligence.service import ProfitIntelligenceService


def _snapshot(value: object) -> object:
    return copy.deepcopy(value)


def test_score_results_preserves_original_price_results() -> None:
    product = Product(name="Bag", brand="Demo", price=100.0, currency="USD", exchange_rate=150.0)
    original = ProfitCalculator().calculate(product, Decimal("50000"))
    original.profit_jpy = Decimal("12345")
    original.profit_margin = Decimal("18.5")
    original.domestic_sale_price_jpy = Decimal("90000")
    original.purchase_price_jpy = Decimal("70000")
    original.metadata = {
        "sales_last_30_days": 10,
        "nested": ["keep", "values"],
        "flags": ("tuple", "values"),
    }
    before = _snapshot(original)
    service = ProfitIntelligenceService()
    service.score_results([original])
    assert original.profit_jpy == before.profit_jpy
    assert original.profit_margin == before.profit_margin
    assert original.domestic_sale_price_jpy == before.domestic_sale_price_jpy
    assert original.purchase_price_jpy == before.purchase_price_jpy
    assert original.metadata == before.metadata
    assert original.metadata["nested"] == before.metadata["nested"]


def test_build_input_does_not_mutate_search_result_or_listing() -> None:
    product = Product(name="Bag", brand="Demo", sku="SKU-1", price=100.0, currency="USD", exchange_rate=150.0)
    listing = MarketplaceListing(
        marketplace_name="demo",
        title="Listing",
        price_jpy=Decimal("50000"),
        source_metadata={"source_style_code": "ABC", "sales_last_30_days": 4},
        match_score=Decimal("0.8"),
    )
    search = MarketplaceSearchResult(
        product=product,
        marketplace_name="demo",
        valid_listings=[listing],
        selected_listing=listing,
        selected_price_jpy=Decimal("50000"),
        metadata={"validation_warning_count": 1},
    )
    result = ProfitCalculator().calculate(product, Decimal("50000"))
    before_listing = _snapshot(listing)
    before_search = _snapshot(search)
    before_product = _snapshot(product)
    service = ProfitIntelligenceService()
    service.build_input(result, search_result=search, listing=listing)
    assert listing == before_listing
    assert search == before_search
    assert product == before_product


def test_scored_return_copies_do_not_alias_original_metadata() -> None:
    product = Product(name="Bag", brand="Demo", price=100.0, currency="USD", exchange_rate=150.0)
    original = ProfitCalculator().calculate(product, Decimal("50000"))
    original.metadata["sales_last_30_days"] = 7
    service = ProfitIntelligenceService()
    scored = service.score_results([original])[0]
    scored.metadata["sales_last_30_days"] = 99
    assert original.metadata["sales_last_30_days"] == 7
