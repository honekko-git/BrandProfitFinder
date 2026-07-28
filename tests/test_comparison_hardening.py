"""Determinism, formatter, and non-mutation tests for comparison."""

import copy
from decimal import Decimal

from comparison.engine import ComparisonEngine
from comparison.formatter import COMPARISON_EXPORT_FIELDS, comparison_result_to_dict
from comparison.models import MarketplaceCandidate
from comparison.ranking import highest_profit_candidate, rank_candidates
from excel.template import MARKETPLACE_COMPARISON_COLUMNS
from models.marketplace_search_result import MarketplaceSearchResult
from models.price_result import CALCULATION_SUCCESS, PriceResult
from models.product import Product
from profit_intelligence.models import ProfitIntelligenceResult


def _candidate(
    marketplace: str,
    *,
    profit: Decimal,
    order_index: int,
    overall_score: float | None = None,
    jpy_comparable: bool = True,
) -> MarketplaceCandidate:
    product = Product(name="Demo", brand="Demo", model="M", sku="S")
    search = MarketplaceSearchResult(
        product=product,
        marketplace_name=marketplace,
        selected_price_jpy=Decimal("10000"),
    )
    price_result = PriceResult(
        product=product,
        profit_jpy=profit,
        profit_margin=Decimal("0.1"),
        calculation_status=CALCULATION_SUCCESS,
        domestic_sale_price_jpy=Decimal("10000"),
    )
    if overall_score is not None:
        price_result.profit_intelligence = ProfitIntelligenceResult(
            overall_score=overall_score,
            confidence_score=80.0,
            risk_score=20.0,
            profit_score=70.0,
            velocity_score=60.0,
            recommendation="Review",
            recommendation_stars=3,
        )
    return MarketplaceCandidate(
        marketplace_name=marketplace,
        search_result=search,
        price_result=price_result,
        listing_currency="JPY",
        source_price_amount=Decimal("10000"),
        jpy_comparable=jpy_comparable,
        order_index=order_index,
    )


def test_export_fields_match_excel_template() -> None:
    assert list(COMPARISON_EXPORT_FIELDS) == MARKETPLACE_COMPARISON_COLUMNS


def test_comparison_repeatability() -> None:
    product = Product(name="Demo", brand="Demo", model="M", sku="S")
    candidates = [
        _candidate("stockx", profit=Decimal("1000"), order_index=0),
        _candidate("goat", profit=Decimal("2000"), order_index=1),
    ]
    engine = ComparisonEngine()
    first = engine.compare_product(product, copy.deepcopy(candidates))
    second = engine.compare_product(product, copy.deepcopy(candidates))
    assert first.selected_review_marketplace == second.selected_review_marketplace
    assert first.warnings == second.warnings
    assert first.recommendation == second.recommendation


def test_engine_does_not_mutate_input_candidates() -> None:
    product = Product(name="Demo", brand="Demo", model="M", sku="S")
    original = _candidate("stockx", profit=Decimal("1000"), order_index=0)
    snapshot = copy.deepcopy(original)
    ComparisonEngine().compare_product(product, [original])
    assert original.match_warnings == snapshot.match_warnings
    assert original.price_result.profit_jpy == snapshot.price_result.profit_jpy


def test_formatter_does_not_mutate_result() -> None:
    product = Product(name="Demo", brand="Demo", model="M", sku="S")
    result = ComparisonEngine().compare_product(
        product,
        [_candidate("stockx", profit=Decimal("1000"), order_index=0)],
    )
    snapshot = copy.deepcopy(result)
    row = comparison_result_to_dict(result)
    assert result.warnings == snapshot.warnings
    assert row["selected_review_profit_jpy"] == 1000.0
    assert row["currency_consistent"] is None or isinstance(row["currency_consistent"], bool)


def test_missing_score_sorts_before_zero_score() -> None:
    with_score_zero = _candidate("stockx", profit=Decimal("1000"), order_index=0, overall_score=0.0)
    without_score = _candidate("goat", profit=Decimal("500"), order_index=1)
    ranked = rank_candidates([without_score, with_score_zero])
    assert ranked[0].marketplace_name == "stockx"


def test_selected_review_can_differ_from_highest_profit() -> None:
    low_profit_high_score = _candidate(
        "stockx",
        profit=Decimal("1000"),
        order_index=0,
        overall_score=95.0,
    )
    high_profit_low_score = _candidate(
        "goat",
        profit=Decimal("5000"),
        order_index=1,
        overall_score=10.0,
    )
    ranked = rank_candidates([low_profit_high_score, high_profit_low_score])
    assert ranked[0].marketplace_name == "stockx"
    highest = highest_profit_candidate([low_profit_high_score, high_profit_low_score])
    assert highest is not None
    assert highest.marketplace_name == "goat"


def test_compatibility_aliases_match_selected_review_fields() -> None:
    product = Product(name="Demo", brand="Demo", model="M", sku="S")
    result = ComparisonEngine().compare_product(
        product,
        [_candidate("stockx", profit=Decimal("1000"), order_index=0)],
    )
    assert result.best_marketplace == result.selected_review_marketplace
    assert result.best_profit_jpy == result.selected_review_profit_jpy
    assert result.best_profit_margin == result.selected_review_profit_margin
