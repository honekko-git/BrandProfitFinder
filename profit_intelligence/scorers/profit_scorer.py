"""Convert PriceResult profit metrics into a normalized discovery profit score."""

from __future__ import annotations

from decimal import Decimal

from models.price_result import CALCULATION_SUCCESS, PriceResult
from profit_intelligence.constants import PROFIT_AMOUNT_THRESHOLDS, PROFIT_MARGIN_THRESHOLDS
from profit_intelligence.discovery_models import ComponentScore
from profit_intelligence.normalization import clamp_score, piecewise_linear_score

ROI_THRESHOLDS: tuple[tuple[float, float], ...] = (
    (0.0, 5.0),
    (10.0, 30.0),
    (25.0, 50.0),
    (50.0, 70.0),
    (100.0, 85.0),
    (200.0, 100.0),
)

NEUTRAL_SCORE = 50.0


class DiscoveryProfitScorer:
    """Score profit amount, margin, and ROI on a 0-100 scale."""

    def score(self, result: PriceResult) -> ComponentScore:
        reasons: list[str] = []
        warnings: list[str] = []

        if result.calculation_status != CALCULATION_SUCCESS:
            warnings.append("Profit calculation was not successful.")
            return ComponentScore(score=0.0, reasons=tuple(), warnings=tuple(warnings))

        subscores: list[float] = []

        profit_jpy = _to_float(result.profit_jpy)
        if profit_jpy is not None:
            if profit_jpy < 0:
                subscores.append(5.0)
                reasons.append("Profit amount indicates a loss.")
                warnings.append("Negative profit amount observed.")
            elif profit_jpy == 0:
                subscores.append(10.0)
                reasons.append("Profit amount is zero.")
            else:
                amount_score = piecewise_linear_score(profit_jpy, PROFIT_AMOUNT_THRESHOLDS)
                subscores.append(amount_score)
                if amount_score >= 70:
                    reasons.append("High absolute profit amount.")
                elif amount_score >= 50:
                    reasons.append("Moderate absolute profit amount.")
                else:
                    reasons.append("Limited absolute profit amount.")
        else:
            warnings.append("Profit amount unavailable.")

        margin = _to_float(result.profit_margin)
        if margin is not None:
            if margin <= 0:
                subscores.append(5.0 if margin < 0 else 10.0)
                reasons.append("Profit margin is not positive.")
            else:
                margin_score = piecewise_linear_score(margin, PROFIT_MARGIN_THRESHOLDS)
                subscores.append(margin_score)
                if margin_score >= 70:
                    reasons.append("High profit margin.")
                elif margin_score >= 50:
                    reasons.append("Moderate profit margin.")
                else:
                    reasons.append("Limited profit margin.")
        else:
            warnings.append("Profit margin unavailable.")

        roi = _to_float(result.roi)
        if roi is not None:
            if roi <= 0:
                subscores.append(5.0 if roi < 0 else 10.0)
                reasons.append("Return on investment is not positive.")
            else:
                roi_score = piecewise_linear_score(roi, ROI_THRESHOLDS)
                subscores.append(roi_score)
                if roi_score >= 70:
                    reasons.append("Strong return on investment.")
        else:
            warnings.append("ROI unavailable.")

        if not subscores:
            warnings.append("No profit metrics available for scoring.")
            return ComponentScore(score=NEUTRAL_SCORE, reasons=tuple(), warnings=tuple(warnings))

        final = clamp_score(sum(subscores) / len(subscores))
        return ComponentScore(
            score=final,
            reasons=tuple(reasons),
            warnings=tuple(warnings),
        )


def _to_float(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    return float(value)
