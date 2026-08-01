"""Scoring helpers for used luxury arbitrage opportunities."""

from __future__ import annotations

from decimal import Decimal

from profit_discovery.arbitrage.models import ArbitrageOpportunity, ArbitrageScore
from profit_intelligence.normalization import clamp_score, piecewise_linear_score

WEIGHT_PROFIT_DIFFERENCE = 0.40
WEIGHT_PROFIT_MARGIN = 0.20
WEIGHT_DEMAND = 0.20
WEIGHT_TURNOVER = 0.20

PROFIT_DIFFERENCE_THRESHOLDS: tuple[tuple[float, float], ...] = (
    (0.0, 0.0),
    (3_000.0, 30.0),
    (8_000.0, 55.0),
    (15_000.0, 75.0),
    (25_000.0, 90.0),
    (40_000.0, 100.0),
)

PROFIT_MARGIN_THRESHOLDS: tuple[tuple[float, float], ...] = (
    (0.0, 0.0),
    (5.0, 25.0),
    (10.0, 45.0),
    (20.0, 65.0),
    (30.0, 85.0),
    (50.0, 100.0),
)


class ArbitrageScorer:
    """Compute arbitrage scores from resolved opportunity metrics."""

    def score(self, opportunity: ArbitrageOpportunity) -> ArbitrageScore:
        """Build one arbitrage score from resolved opportunity values."""
        profit_difference_score = _score_profit_difference(opportunity.price_difference)
        profit_margin_score = _score_profit_margin(opportunity.profit_margin)
        demand_score = clamp_score(opportunity.demand_score)
        turnover_score = clamp_score(opportunity.turnover_score)

        total_score = clamp_score(
            profit_difference_score * WEIGHT_PROFIT_DIFFERENCE
            + profit_margin_score * WEIGHT_PROFIT_MARGIN
            + demand_score * WEIGHT_DEMAND
            + turnover_score * WEIGHT_TURNOVER
        )

        return ArbitrageScore(
            profit_difference_score=profit_difference_score,
            profit_margin_score=profit_margin_score,
            demand_score=demand_score,
            turnover_score=turnover_score,
            total_score=total_score,
        )


def _score_profit_difference(value: Decimal) -> float:
    amount = float(value)
    if amount <= 0:
        return 5.0 if amount < 0 else 10.0
    return piecewise_linear_score(amount, PROFIT_DIFFERENCE_THRESHOLDS)


def _score_profit_margin(value: Decimal) -> float:
    margin = float(value)
    if margin <= 0:
        return 5.0 if margin < 0 else 10.0
    return piecewise_linear_score(margin, PROFIT_MARGIN_THRESHOLDS)
