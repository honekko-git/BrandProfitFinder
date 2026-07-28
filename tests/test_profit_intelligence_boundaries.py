"""Boundary and formula verification tests for Profit Intelligence v1."""

from __future__ import annotations

import pytest

from decimal import Decimal

from profit_intelligence.constants import (
    INSUFFICIENT_DATA_LABEL,
    PROFIT_AMOUNT_THRESHOLDS,
    PROFIT_MARGIN_THRESHOLDS,
    RECOMMENDATION_THRESHOLDS,
)
from profit_intelligence.models import ProfitIntelligenceInput, ScoreComponentResult
from profit_intelligence.normalization import piecewise_linear_score
from profit_intelligence.profit_scorer import ProfitScorer
from profit_intelligence.recommendation_engine import RecommendationEngine


def _component(score: float | None, available: bool = True) -> ScoreComponentResult:
    return ScoreComponentResult(score=score, available=available)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(point, score) for point, score in PROFIT_AMOUNT_THRESHOLDS],
)
def test_profit_amount_threshold_points(value: float, expected: float) -> None:
    assert piecewise_linear_score(value, PROFIT_AMOUNT_THRESHOLDS) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(point, score) for point, score in PROFIT_MARGIN_THRESHOLDS],
)
def test_profit_margin_threshold_points(value: float, expected: float) -> None:
    assert piecewise_linear_score(value, PROFIT_MARGIN_THRESHOLDS) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("low", "high", "midpoint"),
    [
        (0.0, 1000.0, 500.0),
        (1000.0, 3000.0, 2000.0),
        (3000.0, 5000.0, 4000.0),
        (5000.0, 10000.0, 7500.0),
        (10000.0, 20000.0, 15000.0),
    ],
)
def test_profit_amount_between_thresholds(low: float, high: float, midpoint: float) -> None:
    low_score = piecewise_linear_score(low, PROFIT_AMOUNT_THRESHOLDS)
    high_score = piecewise_linear_score(high, PROFIT_AMOUNT_THRESHOLDS)
    mid_score = piecewise_linear_score(midpoint, PROFIT_AMOUNT_THRESHOLDS)
    assert low_score < mid_score < high_score


def test_profit_amount_below_minimum_and_above_maximum() -> None:
    assert piecewise_linear_score(-100.0, PROFIT_AMOUNT_THRESHOLDS) == pytest.approx(5.0)
    assert piecewise_linear_score(50000.0, PROFIT_AMOUNT_THRESHOLDS) == pytest.approx(100.0)


def test_negative_profit_warning_and_zero_profit_wording() -> None:
    scorer = ProfitScorer()
    negative = scorer.score(
        ProfitIntelligenceInput(
            profit_amount_jpy=Decimal("-500"),
            profit_margin_percent=Decimal("-2"),
        )
    )
    zero = scorer.score(
        ProfitIntelligenceInput(
            profit_amount_jpy=Decimal("0"),
            profit_margin_percent=Decimal("0"),
        )
    )
    assert any("loss" in warning.lower() for warning in negative.warnings)
    assert any("zero" in reason.lower() for reason in zero.reasons)
    assert any("zero" in warning.lower() for warning in zero.warnings)


@pytest.mark.parametrize(
    ("overall", "stars"),
    [(threshold.minimum, threshold.stars) for threshold in RECOMMENDATION_THRESHOLDS],
)
def test_recommendation_boundaries_at_minimum(overall: float, stars: int) -> None:
    mapped_stars, _label = RecommendationEngine._map_recommendation(overall)
    assert mapped_stars == stars


def test_recommendation_immediately_below_high_boundary() -> None:
    stars, _label = RecommendationEngine._map_recommendation(89.99)
    assert stars == 4


def test_recommendation_overall_none_maps_to_insufficient_data() -> None:
    engine = RecommendationEngine()
    result = engine.combine(
        _component(None, available=False),
        _component(None, available=False),
        _component(None, available=False),
        _component(10.0),
    )
    assert result.overall_score is None
    assert result.recommendation == INSUFFICIENT_DATA_LABEL
    assert result.recommendation_stars == 0


def test_overall_risk_inversion() -> None:
    engine = RecommendationEngine()
    low_risk = engine.combine(
        _component(80.0),
        _component(None, available=False),
        _component(10.0),
        _component(100.0),
    )
    high_risk = engine.combine(
        _component(80.0),
        _component(None, available=False),
        _component(90.0),
        _component(100.0),
    )
    assert low_risk.overall_score is not None
    assert high_risk.overall_score is not None
    assert low_risk.overall_score > high_risk.overall_score


def test_weight_normalization_when_velocity_unavailable() -> None:
    engine = RecommendationEngine()
    result = engine.combine(
        _component(100.0),
        _component(None, available=False),
        _component(0.0),
        _component(100.0),
    )
    assert result.overall_score == pytest.approx(100.0)


def test_confidence_moderation_levels() -> None:
    engine = RecommendationEngine()
    raw_like = engine.combine(
        _component(100.0),
        _component(100.0),
        _component(0.0),
        _component(100.0),
    )
    half_conf = engine.combine(
        _component(100.0),
        _component(100.0),
        _component(0.0),
        _component(50.0),
    )
    zero_conf = engine.combine(
        _component(100.0),
        _component(100.0),
        _component(0.0),
        _component(0.0),
    )
    assert raw_like.overall_score == pytest.approx(100.0)
    assert half_conf.overall_score == pytest.approx(72.5)
    assert zero_conf.overall_score == pytest.approx(50.0)


def test_overall_score_clamped_to_range() -> None:
    engine = RecommendationEngine()
    result = engine.combine(
        _component(100.0),
        _component(100.0),
        _component(0.0),
        _component(100.0),
    )
    assert 0.0 <= result.overall_score <= 100.0
