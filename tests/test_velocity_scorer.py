"""Tests for velocity scorer."""

from profit_intelligence.models import ProfitIntelligenceInput
from profit_intelligence.velocity_scorer import VelocityScorer


def test_strong_sales_score_high() -> None:
    scorer = VelocityScorer()
    result = scorer.score(
        ProfitIntelligenceInput(
            sales_last_30_days=80,
            sales_last_72_hours=10,
            bids_count=20,
            asks_count=5,
            inventory_count=3,
        )
    )
    assert result.score is not None
    assert result.score >= 70


def test_unknown_sales_not_treated_as_zero() -> None:
    scorer = VelocityScorer()
    result = scorer.score(ProfitIntelligenceInput(bids_count=5, asks_count=2))
    assert "sales_last_30_days" in result.missing_fields


def test_all_market_unknown_returns_none() -> None:
    scorer = VelocityScorer()
    result = scorer.score(ProfitIntelligenceInput())
    assert result.score is None


def test_no_guarantee_language() -> None:
    scorer = VelocityScorer()
    result = scorer.score(
        ProfitIntelligenceInput(sales_last_30_days=100, sales_last_72_hours=20)
    )
    combined = " ".join(result.reasons + result.warnings).lower()
    assert "guarantee" not in combined
    assert "will sell" not in combined
