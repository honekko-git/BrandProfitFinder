"""Formatter tests for product identity export."""

from product_identity.enums import IdentityComparisonLevel, IdentityConfidence, IdentityDecision
from product_identity.formatter import identity_result_to_export_fields
from product_identity.models import ProductIdentityResult


def test_identity_formatter_none_values_blank() -> None:
    row = identity_result_to_export_fields(None)
    assert row["selected_review_identity_decision"] is None
    assert row["selected_review_identity_matched_fields"] == ""


def test_identity_formatter_stable_text() -> None:
    result = ProductIdentityResult(
        decision=IdentityDecision.REVIEW,
        confidence=IdentityConfidence.LOW,
        comparison_level=IdentityComparisonLevel.EXACT_VARIANT,
        identity_score=42.0,
        hard_conflict=False,
        review_required=True,
        family_compatible=None,
        exact_variant_confirmed=None,
        matched_fields=("brand",),
        conflicting_fields=(),
        missing_fields=("jan",),
        reasons=("title similarity only",),
    )
    row = identity_result_to_export_fields(result)
    assert row["selected_review_identity_decision"] == "REVIEW"
    assert row["selected_review_identity_confidence"] == "LOW"
    assert "brand" in str(row["selected_review_identity_matched_fields"])
