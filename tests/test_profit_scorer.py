"""Tests for profit scorer."""

from decimal import Decimal

from profit_intelligence.models import ProfitIntelligenceInput
from profit_intelligence.profit_scorer import ProfitScorer


def test_high_profit_amount_and_margin() -> None:
    scorer = ProfitScorer()
    result = scorer.score(
        ProfitIntelligenceInput(
            profit_amount_jpy=Decimal("20000"),
            profit_margin_percent=Decimal("40"),
        )
    )
    assert result.available is True
    assert result.score is not None
    assert result.score >= 80


def test_negative_profit_warns_and_scores_low() -> None:
    scorer = ProfitScorer()
    result = scorer.score(
        ProfitIntelligenceInput(
            profit_amount_jpy=Decimal("-1000"),
            profit_margin_percent=Decimal("-5"),
        )
    )
    assert result.score is not None
    assert result.score <= 10
    assert any("loss" in warning.lower() for warning in result.warnings)


def test_zero_profit_not_described_as_profitable() -> None:
    scorer = ProfitScorer()
    result = scorer.score(
        ProfitIntelligenceInput(
            profit_amount_jpy=Decimal("0"),
            profit_margin_percent=Decimal("0"),
        )
    )
    assert any("zero" in reason.lower() for reason in result.reasons)


def test_both_unknown_returns_none() -> None:
    scorer = ProfitScorer()
    result = scorer.score(ProfitIntelligenceInput())
    assert result.score is None
    assert result.available is False


def test_amount_only_partial_score() -> None:
    scorer = ProfitScorer()
    result = scorer.score(ProfitIntelligenceInput(profit_amount_jpy=Decimal("10000")))
    assert result.score is not None
    assert "profit_margin_percent" in result.missing_fields
