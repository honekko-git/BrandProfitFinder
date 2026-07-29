"""Ranking score calculation."""

from __future__ import annotations

from decimal import Decimal

from models.price_result import PriceResult
from ranking_foundation.context import RankingBatchContext
from ranking_foundation.policy import RankingPolicy
from ranking_foundation.signals import RankingSignals, extract_ranking_signals


class RankingScoreCalculator:
    """Compute composite ranking scores from policy-weighted signals."""

    def __init__(self, policy: RankingPolicy | None = None) -> None:
        self.policy = policy or RankingPolicy.default()

    def score(self, signals: RankingSignals) -> Decimal:
        """Return composite ranking score for extracted signals."""
        policy = self.policy
        score = (
            signals.profit_margin * policy.profit_margin_weight
            + signals.roi * policy.roi_weight
            + signals.normalized_profit_jpy * policy.profit_jpy_weight
            + signals.identity_confidence * policy.identity_confidence_weight
            + signals.import_cost_score * policy.import_cost_weight
            + signals.marketplace_confidence * policy.marketplace_confidence_weight
        )
        return score.quantize(Decimal("0.01"))

    def score_result(self, result: PriceResult, batch: RankingBatchContext) -> Decimal:
        """Extract signals and compute score for one result."""
        signals = extract_ranking_signals(result, batch)
        return self.score(signals)

    def score_results(self, results: list[PriceResult]) -> list[Decimal]:
        """Score each result using shared batch normalization context."""
        batch = RankingBatchContext.from_results(results)
        return [self.score_result(result, batch) for result in results]
