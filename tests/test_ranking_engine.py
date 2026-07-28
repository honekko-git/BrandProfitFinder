"""Unit tests for price_compare.ranking_engine."""

from decimal import Decimal

from models.price_result import CALCULATION_INVALID_PRICE, CALCULATION_SUCCESS, PriceResult
from models.product import Product
from price_compare.profit_calculator import ProfitCalculator
from price_compare.ranking_engine import RankingEngine, RankingSortKey


def _result(name: str, profit: str, margin: str, roi: str, status: str = CALCULATION_SUCCESS) -> PriceResult:
    return PriceResult(
        product=Product(name=name),
        profit_jpy=Decimal(profit),
        profit_margin=Decimal(margin),
        roi=Decimal(roi),
        domestic_sale_price_jpy=Decimal("80000"),
        total_cost_jpy=Decimal("50000"),
        calculation_status=status,
    )


def test_rank_by_profit_descending() -> None:
    engine = RankingEngine()
    source = [_result("A", "1000", "10", "5"), _result("B", "3000", "20", "10")]
    ranked = engine.rank(source, sort_key=RankingSortKey.PROFIT, descending=True)
    assert [item.product.name for item in ranked] == ["B", "A"]


def test_rank_by_margin() -> None:
    engine = RankingEngine()
    source = [_result("A", "1000", "10", "5"), _result("B", "900", "30", "8")]
    ranked = engine.rank(source, sort_key=RankingSortKey.MARGIN, descending=True)
    assert ranked[0].product.name == "B"


def test_rank_by_roi() -> None:
    engine = RankingEngine()
    source = [_result("A", "1000", "10", "5"), _result("B", "900", "30", "20")]
    ranked = engine.rank(source, sort_key=RankingSortKey.ROI, descending=True)
    assert ranked[0].product.name == "B"


def test_rank_ascending() -> None:
    engine = RankingEngine()
    source = [_result("A", "1000", "10", "5"), _result("B", "3000", "20", "10")]
    ranked = engine.rank(source, sort_key=RankingSortKey.PROFIT, descending=False)
    assert ranked[0].product.name == "A"


def test_top_n_limit() -> None:
    engine = RankingEngine()
    source = [_result("A", "1000", "10", "5"), _result("B", "3000", "20", "10"), _result("C", "2000", "15", "8")]
    ranked = engine.rank(source, sort_key=RankingSortKey.PROFIT, limit=2)
    assert len(ranked) == 2


def test_exclude_invalid_results() -> None:
    engine = RankingEngine()
    source = [
        _result("Bad", "0", "0", "0", status=CALCULATION_INVALID_PRICE),
        _result("Good", "1000", "10", "5"),
    ]
    ranked = engine.rank(source, exclude_invalid=True)
    assert len(ranked) == 1
    assert ranked[0].product.name == "Good"


def test_input_list_not_modified() -> None:
    engine = RankingEngine()
    source = [_result("A", "1000", "10", "5"), _result("B", "3000", "20", "10")]
    original_first_profit = source[0].profit_jpy
    engine.rank(source, sort_key=RankingSortKey.PROFIT)
    assert source[0].profit_jpy == original_first_profit
    assert source[0].product.name == "A"


def test_stable_sort_on_tie() -> None:
    engine = RankingEngine()
    source = [_result("A", "1000", "10", "5"), _result("B", "1000", "12", "6")]
    ranked = engine.rank(source, sort_key=RankingSortKey.PROFIT, descending=True)
    assert [item.product.name for item in ranked] == ["A", "B"]


def test_ranking_score_applied() -> None:
    engine = RankingEngine()
    source = [_result("A", "1000", "10", "5"), _result("B", "3000", "20", "10")]
    ranked = engine.rank(source, sort_key=RankingSortKey.SCORE, descending=True)
    assert ranked[0].ranking_score >= ranked[1].ranking_score


def test_rank_by_total_cost() -> None:
    engine = RankingEngine()
    low = _result("Low", "1000", "10", "5")
    high = _result("High", "1000", "10", "5")
    low.total_cost_jpy = Decimal("40000")
    high.total_cost_jpy = Decimal("60000")
    ranked = engine.rank([low, high], sort_key=RankingSortKey.TOTAL_COST, descending=True)
    assert ranked[0].product.name == "High"
