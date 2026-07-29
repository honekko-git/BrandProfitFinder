"""Phase 24: ranking engine foundation."""

from __future__ import annotations

from decimal import Decimal

from models.price_result import CALCULATION_SUCCESS, PriceResult
from models.product import Product
from price_compare.profit_config import ProfitConfig
from price_compare.ranking_engine import RankingEngine, RankingSortKey
from ranking_foundation.context import RankingBatchContext
from ranking_foundation.policy import RankingPolicy
from ranking_foundation.scorer import RankingScoreCalculator
from ranking_foundation.signals import extract_ranking_signals


def _result(
    name: str,
    profit: str,
    margin: str,
    roi: str,
    *,
    total_cost: str = "50000",
    metadata: dict | None = None,
) -> PriceResult:
    return PriceResult(
        product=Product(name=name),
        profit_jpy=Decimal(profit),
        profit_margin=Decimal(margin),
        roi=Decimal(roi),
        domestic_sale_price_jpy=Decimal("80000"),
        total_cost_jpy=Decimal(total_cost),
        calculation_status=CALCULATION_SUCCESS,
        metadata=metadata or {},
    )


def test_ranking_policy_from_profit_config() -> None:
    config = ProfitConfig(
        ranking_score_profit_margin_weight=Decimal("0.5"),
        ranking_score_roi_weight=Decimal("0.3"),
        ranking_score_profit_jpy_weight=Decimal("0.2"),
        ranking_score_identity_confidence_weight=Decimal("0.1"),
    )
    policy = RankingPolicy.from_profit_config(config)
    assert policy.profit_margin_weight == Decimal("0.5")
    assert policy.identity_confidence_weight == Decimal("0.1")
    assert policy.legacy_only() is False


def test_ranking_policy_default_is_legacy_compatible() -> None:
    policy = RankingPolicy.default()
    assert policy.legacy_only() is True


def test_extract_ranking_signals_identity_and_marketplace_confidence() -> None:
    result = _result(
        "A",
        "1000",
        "10",
        "5",
        metadata={
            "selected_review_identity_confidence": "HIGH",
            "data_completeness": 0.8,
        },
    )
    batch = RankingBatchContext(max_profit_jpy=Decimal("1000"), max_total_cost_jpy=Decimal("50000"))
    signals = extract_ranking_signals(result, batch)
    assert signals.identity_confidence == Decimal("100")
    assert signals.marketplace_confidence == Decimal("80")
    assert signals.import_cost_score == Decimal("0")


def test_import_cost_signal_prefers_lower_total_cost() -> None:
    cheap = _result("Cheap", "1000", "10", "5", total_cost="40000")
    expensive = _result("Expensive", "1000", "10", "5", total_cost="60000")
    batch = RankingBatchContext.from_results([cheap, expensive])
    cheap_signals = extract_ranking_signals(cheap, batch)
    expensive_signals = extract_ranking_signals(expensive, batch)
    assert cheap_signals.import_cost_score > expensive_signals.import_cost_score


def test_ranking_score_calculator_legacy_parity_with_old_engine() -> None:
    config = ProfitConfig(
        ranking_score_profit_margin_weight=Decimal("0.4"),
        ranking_score_roi_weight=Decimal("0.4"),
        ranking_score_profit_jpy_weight=Decimal("0.2"),
    )
    source = [
        _result("A", "1000", "10", "5"),
        _result("B", "3000", "20", "10"),
    ]
    engine = RankingEngine(config)
    ranked = engine.rank(source, sort_key=RankingSortKey.SCORE, descending=True)
    assert ranked[0].product.name == "B"
    assert ranked[0].ranking_score >= ranked[1].ranking_score
    assert ranked[0].ranking_score == Decimal("32.00")


def test_extended_ranking_policy_can_change_order() -> None:
    high_identity = _result(
        "Identity",
        "1000",
        "10",
        "5",
        metadata={"selected_review_identity_confidence": "HIGH", "data_completeness": 1.0},
    )
    high_profit = _result("Profit", "3000", "5", "5")
    policy = RankingPolicy(
        profit_margin_weight=Decimal("0"),
        roi_weight=Decimal("0"),
        profit_jpy_weight=Decimal("0"),
        identity_confidence_weight=Decimal("0.6"),
        marketplace_confidence_weight=Decimal("0.4"),
    )
    calculator = RankingScoreCalculator(policy)
    batch = RankingBatchContext.from_results([high_identity, high_profit])
    identity_score = calculator.score_result(high_identity, batch)
    profit_score = calculator.score_result(high_profit, batch)
    assert identity_score > profit_score


def test_ranking_engine_does_not_mutate_input_list() -> None:
    source = [_result("A", "1000", "10", "5"), _result("B", "3000", "20", "10")]
    original = source[0].profit_jpy
    RankingEngine().rank(source, sort_key=RankingSortKey.PROFIT)
    assert source[0].profit_jpy == original


def test_deterministic_repeated_ranking_scores() -> None:
    source = [_result("A", "1000", "10", "5"), _result("B", "3000", "20", "10")]
    engine = RankingEngine()
    first = engine.rank(source, sort_key=RankingSortKey.SCORE)
    second = engine.rank(source, sort_key=RankingSortKey.SCORE)
    assert [item.ranking_score for item in first] == [item.ranking_score for item in second]
