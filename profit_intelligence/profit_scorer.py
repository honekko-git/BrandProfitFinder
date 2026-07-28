"""
Deterministic profit scoring component.
"""

from __future__ import annotations

from decimal import Decimal

from profit_intelligence.constants import (
    PROFIT_AMOUNT_THRESHOLDS,
    PROFIT_MARGIN_THRESHOLDS,
)
from profit_intelligence.models import ProfitIntelligenceInput, ScoreComponentResult
from profit_intelligence.normalization import (
    clamp_score,
    decimal_to_float,
    dedupe_preserve_order,
    piecewise_linear_score,
)


class ProfitScorer:
    """Score profit amount and margin on a 0-100 scale."""

    def score(self, data: ProfitIntelligenceInput) -> ScoreComponentResult:
        reasons: list[str] = []
        warnings: list[str] = []
        missing: list[str] = []

        amount = data.profit_amount_jpy
        margin = data.profit_margin_percent

        amount_known = amount is not None
        margin_known = margin is not None

        if not amount_known:
            missing.append("profit_amount_jpy")
        if not margin_known:
            missing.append("profit_margin_percent")

        if not amount_known and not margin_known:
            return ScoreComponentResult(
                score=None,
                available=False,
                missing_fields=dedupe_preserve_order(missing),
            )

        subscores: list[float] = []

        if amount_known:
            amount_f = float(amount)  # type: ignore[arg-type]
            if amount_f < 0:
                warnings.append("Observed profit amount is negative (loss).")
                subscores.append(5.0)
                reasons.append("Observed profit amount indicates a loss.")
            elif amount_f == 0:
                warnings.append("Observed profit amount is zero.")
                subscores.append(10.0)
                reasons.append("Observed profit amount is zero, not profitable.")
            else:
                amount_score = piecewise_linear_score(amount_f, PROFIT_AMOUNT_THRESHOLDS)
                subscores.append(amount_score)
                if amount_score >= 70:
                    reasons.append("Observed absolute profit amount is strong.")
                elif amount_score >= 50:
                    reasons.append("Observed absolute profit amount is moderate.")
                else:
                    reasons.append("Observed absolute profit amount is limited.")

        if margin_known:
            margin_f = float(margin)  # type: ignore[arg-type]
            if margin_f <= 0:
                warnings.append("Observed profit margin is not positive.")
                subscores.append(5.0 if margin_f < 0 else 10.0)
                if margin_f < 0:
                    reasons.append("Observed profit margin indicates a loss.")
                else:
                    reasons.append("Observed profit margin is zero.")
            else:
                margin_score = piecewise_linear_score(margin_f, PROFIT_MARGIN_THRESHOLDS)
                subscores.append(margin_score)
                if margin_score >= 70:
                    reasons.append("Observed profit margin is strong.")
                elif margin_score >= 50:
                    reasons.append("Observed profit margin is moderate.")
                else:
                    reasons.append("Observed profit margin is limited.")

        if amount_known and not margin_known:
            warnings.append("Profit score is based on amount only; margin is unavailable.")
        elif margin_known and not amount_known:
            warnings.append("Profit score is based on margin only; amount is unavailable.")

        final = clamp_score(sum(subscores) / len(subscores))

        return ScoreComponentResult(
            score=final,
            available=True,
            reasons=dedupe_preserve_order(reasons),
            warnings=dedupe_preserve_order(warnings),
            missing_fields=dedupe_preserve_order(missing),
        )
