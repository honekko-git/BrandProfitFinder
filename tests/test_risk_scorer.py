"""Tests for risk scorer."""

from decimal import Decimal

from profit_intelligence.models import ProfitIntelligenceInput
from profit_intelligence.risk_scorer import RiskScorer


def test_complete_low_risk_data() -> None:
    scorer = RiskScorer()
    result = scorer.score(
        ProfitIntelligenceInput(
            shipping_cost_known=True,
            marketplace_fee_known=True,
            duties_tax_known=True,
            currency="JPY",
            volatility_percent=Decimal("0.05"),
            style_code_present=True,
            product_id_present=True,
            sales_last_30_days=20,
            asks_count=10,
        )
    )
    assert result.score is not None
    assert result.score <= 20


def test_unknown_shipping_increases_risk() -> None:
    scorer = RiskScorer()
    result = scorer.score(ProfitIntelligenceInput(shipping_cost_known=False))
    assert result.score is not None
    assert result.score >= 8


def test_all_unknown_returns_none() -> None:
    scorer = RiskScorer()
    result = scorer.score(ProfitIntelligenceInput())
    assert result.score is None


def test_no_counterfeit_judgment() -> None:
    scorer = RiskScorer()
    result = scorer.score(
        ProfitIntelligenceInput(
            shipping_cost_known=False,
            style_code_present=False,
            product_id_present=False,
        )
    )
    combined = " ".join(result.reasons + result.warnings).lower()
    assert "counterfeit" not in combined
    assert "authentic" not in combined
