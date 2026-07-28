"""Tests for recommendation engine."""

from profit_intelligence.constants import INSUFFICIENT_DATA_LABEL
from profit_intelligence.models import ScoreComponentResult
from profit_intelligence.recommendation_engine import RecommendationEngine


def _component(score: float | None, available: bool = True) -> ScoreComponentResult:
    return ScoreComponentResult(score=score, available=available)


def test_overall_score_uses_weighted_components() -> None:
    engine = RecommendationEngine()
    result = engine.combine(
        _component(90.0),
        _component(80.0),
        _component(20.0),
        _component(90.0),
    )
    assert result.overall_score is not None
    assert 0 <= result.overall_score <= 100
    assert result.recommendation_stars >= 3


def test_missing_core_component_returns_insufficient_data() -> None:
    engine = RecommendationEngine()
    result = engine.combine(
        _component(None, available=False),
        _component(None, available=False),
        _component(None, available=False),
        _component(50.0),
    )
    assert result.overall_score is None
    assert result.recommendation == INSUFFICIENT_DATA_LABEL
    assert result.recommendation_stars == 0


def test_star_mapping_high_score() -> None:
    engine = RecommendationEngine()
    result = engine.combine(
        _component(95.0),
        _component(95.0),
        _component(5.0),
        _component(95.0),
    )
    assert result.recommendation_stars == 5
    assert "High-priority" in result.recommendation
