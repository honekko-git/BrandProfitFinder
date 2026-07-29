"""Purchase-priority scoring for discovery candidate results."""

from __future__ import annotations

from decimal import Decimal

from models.price_result import CALCULATION_SUCCESS
from profit_discovery.discovery_runner.models import DiscoveryCandidateResult, DiscoveryCandidateStatus
from profit_discovery.opportunity.models import OpportunityResult, OpportunityScore
from profit_intelligence.normalization import clamp_score, piecewise_linear_score

PROFIT_AMOUNT_THRESHOLDS: tuple[tuple[float, float], ...] = (
    (0.0, 5.0),
    (1_000.0, 25.0),
    (3_000.0, 50.0),
    (5_000.0, 70.0),
    (10_000.0, 85.0),
    (20_000.0, 100.0),
)

PROFIT_MARGIN_THRESHOLDS: tuple[tuple[float, float], ...] = (
    (0.0, 5.0),
    (5.0, 25.0),
    (10.0, 50.0),
    (20.0, 70.0),
    (30.0, 85.0),
    (50.0, 100.0),
)

ROI_THRESHOLDS: tuple[tuple[float, float], ...] = (
    (0.0, 5.0),
    (10.0, 30.0),
    (25.0, 50.0),
    (50.0, 70.0),
    (100.0, 85.0),
    (200.0, 100.0),
)

SUPPLIER_RELIABILITY: dict[str, float] = {
    "fashionphile": 90.0,
    "therealreal": 85.0,
    "vestiaire": 85.0,
}

DEFAULT_SUPPLIER_RELIABILITY = 50.0

WEIGHT_PROFIT = 0.30
WEIGHT_MARGIN = 0.20
WEIGHT_ROI = 0.20
WEIGHT_MARKET_CONFIDENCE = 0.20
WEIGHT_SUPPLIER = 0.10


class OpportunityScorer:
    """Compute purchase-priority scores from discovery candidate results."""

    def score(self, candidate: DiscoveryCandidateResult) -> OpportunityScore:
        """Convert one discovery candidate into a weighted opportunity score."""
        profit_score = _score_profit_jpy(candidate)
        margin_score = _score_profit_margin(candidate)
        roi_score = _score_roi(candidate)
        market_confidence_score = _score_market_confidence(candidate)
        supplier_score = _score_supplier_reliability(candidate)

        total_score = clamp_score(
            profit_score * WEIGHT_PROFIT
            + margin_score * WEIGHT_MARGIN
            + roi_score * WEIGHT_ROI
            + market_confidence_score * WEIGHT_MARKET_CONFIDENCE
            + supplier_score * WEIGHT_SUPPLIER
        )

        return OpportunityScore(
            profit_score=profit_score,
            margin_score=margin_score,
            roi_score=roi_score,
            market_confidence_score=market_confidence_score,
            supplier_score=supplier_score,
            total_score=total_score,
        )

    def evaluate(self, candidate: DiscoveryCandidateResult) -> OpportunityResult:
        """Build an opportunity result for one discovery candidate."""
        return OpportunityResult(candidate=candidate, score=self.score(candidate))


def _score_profit_jpy(candidate: DiscoveryCandidateResult) -> float:
    if candidate.status is not DiscoveryCandidateStatus.SUCCESS:
        return 0.0

    profit_result = candidate.profit_result
    if profit_result is None or profit_result.calculation_status != CALCULATION_SUCCESS:
        return 0.0

    profit_jpy = _to_float(profit_result.profit_jpy)
    if profit_jpy is None:
        return 0.0
    if profit_jpy <= 0:
        return 5.0 if profit_jpy < 0 else 10.0
    return piecewise_linear_score(profit_jpy, PROFIT_AMOUNT_THRESHOLDS)


def _score_profit_margin(candidate: DiscoveryCandidateResult) -> float:
    if candidate.status is not DiscoveryCandidateStatus.SUCCESS:
        return 0.0

    profit_result = candidate.profit_result
    if profit_result is None or profit_result.calculation_status != CALCULATION_SUCCESS:
        return 0.0

    margin = _to_float(profit_result.profit_margin)
    if margin is None:
        return 0.0
    if margin <= 0:
        return 5.0 if margin < 0 else 10.0
    return piecewise_linear_score(margin, PROFIT_MARGIN_THRESHOLDS)


def _score_roi(candidate: DiscoveryCandidateResult) -> float:
    if candidate.status is not DiscoveryCandidateStatus.SUCCESS:
        return 0.0

    profit_result = candidate.profit_result
    if profit_result is None or profit_result.calculation_status != CALCULATION_SUCCESS:
        return 0.0

    roi = _to_float(profit_result.roi)
    if roi is None:
        return 0.0
    if roi <= 0:
        return 5.0 if roi < 0 else 10.0
    return piecewise_linear_score(roi, ROI_THRESHOLDS)


def _score_market_confidence(candidate: DiscoveryCandidateResult) -> float:
    market_evaluation = candidate.market_evaluation
    if market_evaluation is None:
        return 0.0

    confidence = market_evaluation.confidence_score
    if confidence <= 1.0:
        return clamp_score(confidence * 100.0)
    return clamp_score(confidence)


def _score_supplier_reliability(candidate: DiscoveryCandidateResult) -> float:
    supplier_name = candidate.supplier_product.supplier_name.strip().lower()
    return SUPPLIER_RELIABILITY.get(supplier_name, DEFAULT_SUPPLIER_RELIABILITY)


def _to_float(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    return float(value)
