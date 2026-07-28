"""
Deterministic market velocity scoring component.
"""

from __future__ import annotations

from profit_intelligence.constants import SALES_30D_THRESHOLDS, SALES_72H_THRESHOLDS
from profit_intelligence.models import ProfitIntelligenceInput, ScoreComponentResult
from profit_intelligence.normalization import (
    clamp_score,
    dedupe_preserve_order,
    piecewise_linear_score,
)


class VelocityScorer:
    """Score observed market activity and demand signals."""

    def score(self, data: ProfitIntelligenceInput) -> ScoreComponentResult:
        reasons: list[str] = []
        warnings: list[str] = []
        missing: list[str] = []

        sales_30 = data.sales_last_30_days
        sales_72 = data.sales_last_72_hours
        bids = data.bids_count
        asks = data.asks_count
        inventory = data.inventory_count

        signals: list[tuple[float, float]] = []

        if sales_30 is not None:
            s30 = piecewise_linear_score(float(sales_30), SALES_30D_THRESHOLDS)
            signals.append((s30, 0.40))
            if s30 >= 70:
                reasons.append("Strong 30-day sales activity in available data.")
            elif s30 >= 40:
                reasons.append("Moderate 30-day sales activity in available data.")
            else:
                reasons.append("Limited 30-day sales activity in available data.")
        else:
            missing.append("sales_last_30_days")

        if sales_72 is not None:
            s72 = piecewise_linear_score(float(sales_72), SALES_72H_THRESHOLDS)
            signals.append((s72, 0.25))
            if s72 >= 60:
                reasons.append("Recent 72-hour sales activity supports demand signals.")
            else:
                reasons.append("Recent sales activity is limited in available data.")
        else:
            missing.append("sales_last_72_hours")

        if bids is not None and asks is not None:
            if asks == 0 and bids > 0:
                balance_score = 85.0
                reasons.append("Bid demand exceeds visible ask supply in available data.")
            elif bids > asks:
                balance_score = 75.0
                reasons.append("Bid demand exceeds visible ask supply in available data.")
            elif asks > 0 and bids / asks >= 0.5:
                balance_score = 55.0
            elif asks > bids * 2:
                balance_score = 25.0
                reasons.append("Ask supply appears high relative to bid demand.")
            else:
                balance_score = 40.0
            signals.append((balance_score, 0.20))
        else:
            if bids is None:
                missing.append("bids_count")
            if asks is None:
                missing.append("asks_count")

        if inventory is not None and sales_30 is not None:
            if sales_30 == 0 and inventory > 5:
                inv_score = 15.0
                reasons.append("Inventory appears high relative to observed demand.")
            elif sales_30 > 0:
                ratio = inventory / max(sales_30, 1)
                if ratio > 3:
                    inv_score = 30.0
                    reasons.append("Inventory appears high relative to observed demand.")
                elif ratio > 1.5:
                    inv_score = 50.0
                else:
                    inv_score = 75.0
            else:
                inv_score = 40.0
            signals.append((inv_score, 0.15))
        elif inventory is not None:
            missing.append("sales_last_30_days")
        else:
            missing.append("inventory_count")

        if not signals:
            return ScoreComponentResult(
                score=None,
                available=False,
                missing_fields=dedupe_preserve_order(missing),
                warnings=("Insufficient market activity data for velocity scoring.",),
            )

        total_weight = sum(weight for _, weight in signals)
        weighted = sum(score * weight for score, weight in signals) / total_weight
        final = clamp_score(weighted)

        if len(missing) > 0:
            warnings.append("Velocity score is based on incomplete market information.")

        return ScoreComponentResult(
            score=final,
            available=True,
            reasons=dedupe_preserve_order(reasons),
            warnings=dedupe_preserve_order(warnings),
            missing_fields=dedupe_preserve_order(missing),
        )
