"""Tests for comparison ranking."""

from decimal import Decimal

from comparison.engine import ComparisonEngine
from comparison.models import MarketplaceCandidate
from comparison.ranking import rank_candidates, rank_comparison_results
from models.marketplace_search_result import MarketplaceSearchResult
from models.price_result import CALCULATION_SUCCESS, PriceResult
from models.product import Product
from profit_intelligence.models import ProfitIntelligenceResult


def _candidate(
    marketplace: str,
    profit: Decimal,
    *,
    order_index: int,
    warnings: int = 0,
    completeness: float = 50,
    overall_score: int | None = None,
) -> MarketplaceCandidate:
    product = Product(name="Demo", brand="Demo", model="M", sku="S")
    search = MarketplaceSearchResult(
        product=product,
        marketplace_name=marketplace,
        selected_price_jpy=Decimal("10000"),
        metadata={"warnings": ["w"] * warnings},
    )
    price_result = PriceResult(
        product=product,
        profit_jpy=profit,
        profit_margin=Decimal("0.1"),
        calculation_status=CALCULATION_SUCCESS,
        domestic_sale_price_jpy=Decimal("10000"),
        metadata={"data_completeness": completeness},
    )
    if overall_score is not None:
        price_result.profit_intelligence = ProfitIntelligenceResult(
            overall_score=float(overall_score),
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
        jpy_comparable=True,
        order_index=order_index,
    )


def test_rank_candidates_deterministic() -> None:
    candidates = [
        _candidate("a", Decimal("1000"), order_index=0),
        _candidate("b", Decimal("2000"), order_index=1, warnings=2),
        _candidate("c", Decimal("1500"), order_index=2),
    ]
    first = rank_candidates(candidates)
    second = rank_candidates(candidates)
    assert [item.marketplace_name for item in first] == [item.marketplace_name for item in second]
    assert first[0].marketplace_name == "b"


def test_rank_candidates_profit_before_completeness() -> None:
    low_profit = _candidate("stockx", Decimal("1000"), order_index=0, completeness=99)
    high_profit = _candidate("goat", Decimal("5000"), order_index=1, completeness=10)
    ranked = rank_candidates([low_profit, high_profit])
    assert ranked[0].marketplace_name == "goat"


def test_rank_candidates_intelligence_before_profit() -> None:
    lower_profit = _candidate(
        "stockx",
        Decimal("1000"),
        order_index=0,
        overall_score=90,
    )
    higher_profit = _candidate(
        "goat",
        Decimal("5000"),
        order_index=1,
        overall_score=50,
    )
    ranked = rank_candidates([lower_profit, higher_profit])
    assert ranked[0].marketplace_name == "stockx"


def test_non_comparable_candidates_rank_last() -> None:
    jpy = _candidate("stockx", Decimal("1000"), order_index=0)
    usd = _candidate("goat", Decimal("99999"), order_index=1)
    usd.jpy_comparable = False
    ranked = rank_candidates([usd, jpy])
    assert ranked[0].marketplace_name == "stockx"


def test_rank_comparison_results_stable_order() -> None:
    product = Product(name="A", brand="B", model="M", sku="S")
    comparison = ComparisonEngine().compare_product(
        product,
        [
            _candidate("stockx", Decimal("1000"), order_index=0),
            _candidate("goat", Decimal("3000"), order_index=1),
        ],
    )
    ranked = rank_comparison_results([comparison])
    assert len(ranked) == 1
    assert ranked[0].profit_jpy == Decimal("3000")


def test_rank_tie_breaks_on_original_order() -> None:
    first = _candidate("stockx", Decimal("1000"), order_index=0)
    second = _candidate("goat", Decimal("1000"), order_index=1)
    ranked = rank_candidates([first, second])
    assert ranked[0].marketplace_name == "stockx"
