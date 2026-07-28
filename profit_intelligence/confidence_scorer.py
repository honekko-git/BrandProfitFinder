"""
Deterministic data-completeness confidence scoring.
"""

from __future__ import annotations

from profit_intelligence.models import ProfitIntelligenceInput, ScoreComponentResult
from profit_intelligence.normalization import clamp_score, dedupe_preserve_order


class ConfidenceScorer:
    """Score data completeness and scoring reliability (not success probability)."""

    _FINANCIAL_FIELDS: tuple[tuple[str, float], ...] = (
        ("profit_amount_jpy", 12.0),
        ("profit_margin_percent", 12.0),
        ("domestic_sale_price_jpy", 8.0),
        ("overseas_purchase_price_jpy", 8.0),
        ("shipping_cost_known", 5.0),
        ("marketplace_fee_known", 5.0),
        ("duties_tax_known", 5.0),
        ("currency", 5.0),
    )

    _MARKET_FIELDS: tuple[tuple[str, float], ...] = (
        ("sales_last_30_days", 10.0),
        ("sales_last_72_hours", 8.0),
        ("bids_count", 5.0),
        ("asks_count", 5.0),
        ("volatility_percent", 4.0),
        ("inventory_count", 3.0),
    )

    _IDENTITY_FIELDS: tuple[tuple[str, float], ...] = (
        ("style_code_present", 4.0),
        ("product_id_present", 4.0),
        ("jan_present", 3.0),
        ("identifier_match_strength", 4.0),
        ("title_match_strength", 3.0),
        ("size_match", 4.0),
    )

    _QUALITY_FIELDS: tuple[tuple[str, float], ...] = (
        ("listing_count", 3.0),
        ("source_count", 3.0),
    )

    def score(self, data: ProfitIntelligenceInput) -> ScoreComponentResult:
        reasons: list[str] = []
        warnings: list[str] = []
        missing: list[str] = []
        earned = 0.0
        possible = 0.0

        def evaluate_group(
            fields: tuple[tuple[str, float], ...],
            group_label: str,
        ) -> None:
            nonlocal earned, possible
            group_earned = 0.0
            group_possible = 0.0
            for field_name, weight in fields:
                group_possible += weight
                value = getattr(data, field_name)
                if self._field_available(field_name, value):
                    group_earned += weight
                else:
                    missing.append(field_name)
            possible += group_possible
            earned += group_earned
            if group_earned >= group_possible * 0.7:
                reasons.append(f"{group_label} data is largely complete.")
            elif group_earned == 0:
                warnings.append(f"{group_label} data is largely unavailable.")

        evaluate_group(self._FINANCIAL_FIELDS, "Financial")
        evaluate_group(self._MARKET_FIELDS, "Market activity")
        evaluate_group(self._IDENTITY_FIELDS, "Identity and matching")
        evaluate_group(self._QUALITY_FIELDS, "Listing quality")

        if data.validation_warning_count is not None and data.validation_warning_count > 0:
            penalty = min(15.0, data.validation_warning_count * 3.0)
            earned = max(0.0, earned - penalty)
            warnings.append("Validation warnings reduce data-completeness confidence.")

        if possible == 0:
            final = 0.0
        else:
            final = clamp_score(earned / possible * 100.0)

        reasons.append(
            "Confidence reflects data completeness, not predicted profitability."
        )

        return ScoreComponentResult(
            score=final,
            available=True,
            reasons=dedupe_preserve_order(reasons),
            warnings=dedupe_preserve_order(warnings),
            missing_fields=dedupe_preserve_order(missing),
        )

    @staticmethod
    def _field_available(field_name: str, value: object) -> bool:
        if field_name.endswith("_known") or field_name.endswith("_present"):
            return value is True
        if field_name == "size_match":
            return value is not None
        if field_name == "currency":
            return isinstance(value, str) and bool(value.strip())
        return value is not None
