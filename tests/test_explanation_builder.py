"""Tests for explanation builder."""

from profit_intelligence.explanation_builder import ExplanationBuilder
from profit_intelligence.models import ScoreComponentResult


def test_explanation_builder_deduplicates_and_orders() -> None:
    builder = ExplanationBuilder()
    reasons, warnings, missing = builder.build(
        {
            "profit": ScoreComponentResult(
                score=70.0,
                available=True,
                reasons=("Strong margin.", "Strong margin."),
                warnings=("Partial data.",),
                missing_fields=("sales_last_30_days",),
            ),
            "velocity": ScoreComponentResult(
                score=60.0,
                available=True,
                reasons=("Moderate sales.",),
                warnings=("Partial data.",),
            ),
        }
    )
    assert reasons == ("Strong margin.", "Moderate sales.")
    assert warnings == ("Partial data.",)
    assert "sales_last_30_days" in missing
