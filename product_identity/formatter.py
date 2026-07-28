"""Format product identity results for export."""

from __future__ import annotations

from product_identity.models import ProductIdentityResult


def identity_result_to_export_fields(result: ProductIdentityResult | None) -> dict[str, object]:
    """Serialize selected-review identity fields for Excel export."""
    if result is None:
        return {
            "selected_review_identity_decision": None,
            "selected_review_identity_confidence": None,
            "selected_review_identity_score": None,
            "selected_review_identity_review_required": None,
            "selected_review_identity_matched_fields": "",
            "selected_review_identity_conflicting_fields": "",
            "selected_review_identity_missing_fields": "",
            "selected_review_identity_reasons": "",
        }
    return {
        "selected_review_identity_decision": result.decision.value,
        "selected_review_identity_confidence": result.confidence.value,
        "selected_review_identity_score": result.identity_score,
        "selected_review_identity_review_required": result.review_required,
        "selected_review_identity_matched_fields": ", ".join(result.matched_fields),
        "selected_review_identity_conflicting_fields": ", ".join(result.conflicting_fields),
        "selected_review_identity_missing_fields": ", ".join(result.missing_fields),
        "selected_review_identity_reasons": " | ".join(result.reasons),
    }
