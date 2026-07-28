"""Determinism and stable ordering tests for Profit Intelligence v1."""

from __future__ import annotations

import copy
import dataclasses
from decimal import Decimal

from models.product import Product
from price_compare.profit_calculator import ProfitCalculator
from profit_intelligence.explanation_builder import ExplanationBuilder
from profit_intelligence.models import ProfitIntelligenceInput, ScoreComponentResult
from profit_intelligence.normalization import dedupe_preserve_order, piecewise_linear_score
from profit_intelligence.profit_scorer import ProfitScorer
from profit_intelligence.service import ProfitIntelligenceService, rank_by_intelligence_score


def test_identical_input_produces_identical_results() -> None:
    service = ProfitIntelligenceService()
    data = ProfitIntelligenceInput(
        profit_amount_jpy=Decimal("8000"),
        profit_margin_percent=Decimal("22"),
        sales_last_30_days=12,
        shipping_cost_known=True,
        marketplace_fee_known=True,
        duties_tax_known=True,
        currency="JPY",
    )
    first = service.score_input(data)
    second = service.score_input(copy.deepcopy(data))
    assert first == second


def test_component_scorers_are_deterministic() -> None:
    scorer = ProfitScorer()
    data = ProfitIntelligenceInput(
        profit_amount_jpy=Decimal("5000"),
        profit_margin_percent=Decimal("15"),
    )
    assert scorer.score(data) == scorer.score(copy.deepcopy(data))


def test_explanation_ordering_is_stable() -> None:
    builder = ExplanationBuilder()
    components = {
        "profit": ScoreComponentResult(
            score=70.0,
            available=True,
            reasons=("Observed profit margin is strong.",),
            warnings=("Partial data.",),
            missing_fields=("sales_last_30_days",),
        ),
        "velocity": ScoreComponentResult(
            score=60.0,
            available=True,
            reasons=("Moderate 30-day sales activity in available data.",),
            warnings=("Partial data.",),
            missing_fields=("inventory_count",),
        ),
        "risk": ScoreComponentResult(
            score=15.0,
            available=True,
            reasons=("Observed risk signals are limited in available data.",),
        ),
        "confidence": ScoreComponentResult(
            score=55.0,
            available=True,
            reasons=("Financial data is largely complete.",),
        ),
    }
    first = builder.build(components)
    second = builder.build(copy.deepcopy(components))
    assert first == second
    assert first[0][0] == "Observed profit margin is strong."


def test_duplicate_messages_removed_with_first_occurrence_order() -> None:
    assert dedupe_preserve_order(["b", "a", "b", "c", "a"]) == ("b", "a", "c")


def _with_overall_score(scored: list, overall: float):
    adjusted = []
    for item in scored:
        clone = copy.deepcopy(item)
        assert clone.profit_intelligence is not None
        clone.profit_intelligence = dataclasses.replace(
            clone.profit_intelligence,
            overall_score=overall,
        )
        adjusted.append(clone)
    return adjusted


def test_equal_overall_scores_preserve_original_order() -> None:
    product_a = Product(name="Alpha", brand="Demo", price=100.0, currency="USD", exchange_rate=150.0)
    product_b = Product(name="Beta", brand="Demo", price=100.0, currency="USD", exchange_rate=150.0)
    calc = ProfitCalculator()
    result_a = calc.calculate(product_a, Decimal("50000"))
    result_b = calc.calculate(product_b, Decimal("48000"))
    service = ProfitIntelligenceService()
    scored = _with_overall_score(service.score_results([result_a, result_b]), 75.0)
    ranked = rank_by_intelligence_score(scored)
    assert [item.product.name if item.product else "" for item in ranked] == ["Alpha", "Beta"]


def test_ranking_tie_breaks_on_profit_then_original_order() -> None:
    product_a = Product(name="Alpha", brand="Demo", price=100.0, currency="USD", exchange_rate=150.0)
    product_b = Product(name="Beta", brand="Demo", price=100.0, currency="USD", exchange_rate=150.0)
    calc = ProfitCalculator()
    result_a = calc.calculate(product_a, Decimal("50000"))
    result_b = calc.calculate(product_b, Decimal("60000"))
    service = ProfitIntelligenceService()
    scored = _with_overall_score(service.score_results([result_a, result_b]), 80.0)
    ranked = rank_by_intelligence_score(scored)
    assert ranked[0].profit_jpy > ranked[1].profit_jpy


def test_piecewise_threshold_boundaries_are_stable() -> None:
    thresholds = ((0.0, 5.0), (1000.0, 25.0), (3000.0, 50.0))
    assert piecewise_linear_score(1000.0, thresholds) == 25.0
    assert piecewise_linear_score(2000.0, thresholds) == 37.5
