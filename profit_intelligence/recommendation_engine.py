"""
Combine component scores into an overall score and recommendation.
"""

from __future__ import annotations

from profit_intelligence.constants import (
    INSUFFICIENT_DATA_LABEL,
    RECOMMENDATION_THRESHOLDS,
    ComponentWeights,
)
from profit_intelligence.models import ProfitIntelligenceResult, ScoreComponentResult
from profit_intelligence.normalization import clamp_score


class RecommendationEngine:
    """
    Combine available component scores into an overall moderated score.

    Formula:
    1. raw = renormalized weighted sum of profit, velocity, (100 - risk), confidence
    2. moderated = 50 + (raw - 50) * (confidence / 100)
    """

    def __init__(self, weights: ComponentWeights | None = None) -> None:
        self.weights = weights or ComponentWeights()

    def combine(
        self,
        profit: ScoreComponentResult,
        velocity: ScoreComponentResult,
        risk: ScoreComponentResult,
        confidence: ScoreComponentResult,
        *,
        reasons: tuple[str, ...] = (),
        warnings: tuple[str, ...] = (),
        missing_fields: tuple[str, ...] = (),
    ) -> ProfitIntelligenceResult:
        evaluated: list[str] = []
        unavailable: list[str] = []

        weighted_sum = 0.0
        total_weight = 0.0

        core_available = False

        if profit.available and profit.score is not None:
            weighted_sum += profit.score * self.weights.profit
            total_weight += self.weights.profit
            evaluated.append("profit")
            core_available = True
        else:
            unavailable.append("profit")

        if velocity.available and velocity.score is not None:
            weighted_sum += velocity.score * self.weights.velocity
            total_weight += self.weights.velocity
            evaluated.append("velocity")
            core_available = True
        else:
            unavailable.append("velocity")

        if risk.available and risk.score is not None:
            risk_inverse = 100.0 - risk.score
            weighted_sum += risk_inverse * self.weights.risk_inverse
            total_weight += self.weights.risk_inverse
            evaluated.append("risk")
            core_available = True
        else:
            unavailable.append("risk")

        confidence_score = confidence.score if confidence.score is not None else 0.0
        if confidence.available:
            weighted_sum += confidence_score * self.weights.confidence
            total_weight += self.weights.confidence
            evaluated.append("confidence")
        else:
            unavailable.append("confidence")

        if not core_available or total_weight == 0:
            return ProfitIntelligenceResult(
                overall_score=None,
                profit_score=profit.score,
                velocity_score=velocity.score,
                risk_score=risk.score,
                confidence_score=confidence_score,
                recommendation=INSUFFICIENT_DATA_LABEL,
                recommendation_stars=0,
                reasons=reasons,
                warnings=warnings,
                missing_fields=missing_fields,
                evaluated_components=tuple(evaluated),
                unavailable_components=tuple(unavailable),
            )

        raw_score = weighted_sum / total_weight
        confidence_ratio = confidence_score / 100.0
        moderated = 50.0 + (raw_score - 50.0) * confidence_ratio
        overall = clamp_score(moderated)

        stars, label = self._map_recommendation(overall)

        return ProfitIntelligenceResult(
            overall_score=overall,
            profit_score=profit.score,
            velocity_score=velocity.score,
            risk_score=risk.score,
            confidence_score=confidence_score,
            recommendation=label,
            recommendation_stars=stars,
            reasons=reasons,
            warnings=warnings,
            missing_fields=missing_fields,
            evaluated_components=tuple(evaluated),
            unavailable_components=tuple(unavailable),
        )

    @staticmethod
    def _map_recommendation(overall: float) -> tuple[int, str]:
        for threshold in RECOMMENDATION_THRESHOLDS:
            if overall >= threshold.minimum:
                return threshold.stars, threshold.label
        return 1, RECOMMENDATION_THRESHOLDS[-1].label
