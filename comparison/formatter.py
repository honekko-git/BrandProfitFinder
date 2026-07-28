"""
Format cross-marketplace comparison results for export and logging.
"""

from __future__ import annotations

from decimal import Decimal

from comparison.models import ProductComparisonResult
from product_identity.formatter import identity_result_to_export_fields

SELECTED_REVIEW_IDENTITY_EXPORT_FIELDS: tuple[str, ...] = (
    "selected_review_identity_decision",
    "selected_review_identity_confidence",
    "selected_review_identity_score",
    "selected_review_identity_review_required",
    "selected_review_identity_matched_fields",
    "selected_review_identity_conflicting_fields",
    "selected_review_identity_missing_fields",
    "selected_review_identity_reasons",
)

# Stable export field order. Must stay aligned with excel.template.MARKETPLACE_COMPARISON_COLUMNS.
COMPARISON_EXPORT_FIELDS: tuple[str, ...] = (
    "product_name",
    "product_brand",
    "product_sku",
    "selected_review_marketplace",
    "selected_review_profit_jpy",
    "selected_review_margin",
    "highest_profit_marketplace",
    "highest_profit_jpy",
    "highest_profit_margin",
    "marketplaces_compared",
    "marketplaces_supported",
    "marketplaces_missing",
    "highest_overall_score",
    "highest_confidence_score",
    "highest_data_completeness",
    "highest_risk_score",
    "currencies_observed",
    "currency_consistent",
    "price_consistent",
    "warning_summary",
    "validation_summary",
    "comparison_reliability",
    "recommendation",
    *SELECTED_REVIEW_IDENTITY_EXPORT_FIELDS,
)


def _decimal_to_export(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _bool_to_export(value: bool | None) -> bool | None:
    return value


def comparison_result_to_dict(result: ProductComparisonResult) -> dict[str, object]:
    """Serialize one product comparison row for Excel export."""
    product = result.product
    selected_identity = _selected_candidate_identity(result)
    row = {
        "product_name": product.name if product else "",
        "product_brand": product.brand if product else "",
        "product_sku": product.sku if product else "",
        "selected_review_marketplace": result.selected_review_marketplace,
        "selected_review_profit_jpy": _decimal_to_export(result.selected_review_profit_jpy),
        "selected_review_margin": _decimal_to_export(result.selected_review_margin),
        "highest_profit_marketplace": result.highest_profit_marketplace,
        "highest_profit_jpy": _decimal_to_export(result.highest_profit_jpy),
        "highest_profit_margin": _decimal_to_export(result.highest_profit_margin),
        "marketplaces_compared": ", ".join(result.marketplaces_compared),
        "marketplaces_supported": ", ".join(result.supported_marketplaces),
        "marketplaces_missing": ", ".join(result.missing_marketplaces),
        "highest_overall_score": result.best_overall_score,
        "highest_confidence_score": result.best_confidence_score,
        "highest_data_completeness": result.best_data_completeness,
        "highest_risk_score": result.best_risk_score,
        "currencies_observed": ", ".join(result.currencies_observed),
        "currency_consistent": _bool_to_export(result.currency_consistent),
        "price_consistent": _bool_to_export(result.price_consistent),
        "warning_summary": " | ".join(result.warnings),
        "validation_summary": result.validation_summary,
        "comparison_reliability": result.comparison_reliability,
        "recommendation": result.recommendation,
    }
    row.update(identity_result_to_export_fields(selected_identity))
    return row


def _selected_candidate_identity(result: ProductComparisonResult):
    if not result.selected_review_marketplace:
        return None
    for candidate in result.candidates:
        if candidate.marketplace_name == result.selected_review_marketplace:
            return candidate.identity_result
    return None
