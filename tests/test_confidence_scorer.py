"""Tests for confidence scorer."""

from decimal import Decimal

from profit_intelligence.models import ProfitIntelligenceInput
from profit_intelligence.confidence_scorer import ConfidenceScorer


def test_highly_complete_data() -> None:
    scorer = ConfidenceScorer()
    result = scorer.score(
        ProfitIntelligenceInput(
            profit_amount_jpy=Decimal("5000"),
            profit_margin_percent=Decimal("20"),
            domestic_sale_price_jpy=Decimal("50000"),
            overseas_purchase_price_jpy=Decimal("30000"),
            currency="JPY",
            shipping_cost_known=True,
            marketplace_fee_known=True,
            duties_tax_known=True,
            sales_last_30_days=10,
            sales_last_72_hours=2,
            bids_count=5,
            asks_count=3,
            style_code_present=True,
            product_id_present=True,
            jan_present=True,
            size_match=True,
            listing_count=3,
            source_count=2,
        )
    )
    assert result.score >= 70


def test_sparse_data_lower_confidence() -> None:
    scorer = ConfidenceScorer()
    result = scorer.score(ProfitIntelligenceInput(profit_amount_jpy=Decimal("1000")))
    assert result.score < 50


def test_confidence_not_probability_language() -> None:
    scorer = ConfidenceScorer()
    result = scorer.score(ProfitIntelligenceInput(profit_amount_jpy=Decimal("1000")))
    combined = " ".join(result.reasons).lower()
    assert "probability" not in combined
    assert "predicted success" not in combined
