"""Validation scoring and buy decision rules for profit discovery."""

from __future__ import annotations

from decimal import Decimal

from profit_discovery.discovery_validation.models import ValidationConfig, ValidationOpportunity, ValidationScore
from profit_discovery.models import BuyDecision
from profit_intelligence.normalization import clamp_score, piecewise_linear_score

WEIGHT_PROFIT = 0.40
WEIGHT_MARGIN = 0.20
WEIGHT_DEMAND = 0.20
WEIGHT_TURNOVER = 0.20

PROFIT_THRESHOLDS: tuple[tuple[float, float], ...] = (
    (0.0, 0.0),
    (3_000.0, 30.0),
    (8_000.0, 55.0),
    (10_000.0, 65.0),
    (15_000.0, 75.0),
    (25_000.0, 90.0),
    (40_000.0, 100.0),
)

MARGIN_THRESHOLDS: tuple[tuple[float, float], ...] = (
    (0.0, 0.0),
    (5.0, 25.0),
    (10.0, 45.0),
    (20.0, 65.0),
    (30.0, 85.0),
    (50.0, 100.0),
)


class ProfitValidationValidator:
    """Score and classify profit validation opportunities."""

    def __init__(self, *, config: ValidationConfig | None = None) -> None:
        self._config = config or ValidationConfig()

    @property
    def config(self) -> ValidationConfig:
        return self._config

    def score(self, opportunity: ValidationOpportunity) -> ValidationScore:
        """Compute one weighted validation score."""
        profit_score = _score_profit(opportunity.estimated_profit)
        margin_score = _score_margin(opportunity.profit_margin)
        demand_score = clamp_score(opportunity.demand_score)
        turnover_score = clamp_score(opportunity.turnover_score)
        total_score = clamp_score(
            profit_score * WEIGHT_PROFIT
            + margin_score * WEIGHT_MARGIN
            + demand_score * WEIGHT_DEMAND
            + turnover_score * WEIGHT_TURNOVER
        )
        return ValidationScore(
            profit_score=profit_score,
            margin_score=margin_score,
            demand_score=demand_score,
            turnover_score=turnover_score,
            total_score=total_score,
        )

    def decide(self, opportunity: ValidationOpportunity) -> str:
        """Return BUY, HOLD, or PASS based on validation thresholds."""
        profit_ok = opportunity.estimated_profit >= self._config.minimum_profit_jpy
        demand_ok = opportunity.demand_score >= self._config.minimum_demand_score
        if profit_ok and demand_ok:
            return BuyDecision.BUY.value
        if profit_ok or demand_ok:
            return BuyDecision.HOLD.value
        return BuyDecision.PASS.value

    def validate_one(self, opportunity: ValidationOpportunity) -> ValidationOpportunity:
        """Apply scoring and decision to one validation opportunity."""
        score = self.score(opportunity)
        decision = self.decide(opportunity)
        return ValidationOpportunity(
            product=opportunity.product,
            brand=opportunity.brand,
            category=opportunity.category,
            purchase_source=opportunity.purchase_source,
            purchase_price=opportunity.purchase_price,
            purchase_url=opportunity.purchase_url,
            domestic_market=opportunity.domestic_market,
            domestic_price=opportunity.domestic_price,
            domestic_url=opportunity.domestic_url,
            estimated_profit=opportunity.estimated_profit,
            profit_margin=opportunity.profit_margin,
            demand_score=opportunity.demand_score,
            turnover_score=opportunity.turnover_score,
            validation_score=score.total_score,
            decision=decision,
            external_id=opportunity.external_id,
            recommendation_rank=opportunity.recommendation_rank,
        )


def _score_profit(value: Decimal) -> float:
    amount = float(value)
    if amount <= 0:
        return 5.0 if amount < 0 else 10.0
    return piecewise_linear_score(amount, PROFIT_THRESHOLDS)


def _score_margin(value: Decimal) -> float:
    margin = float(value)
    if margin <= 0:
        return 5.0 if margin < 0 else 10.0
    return piecewise_linear_score(margin, MARGIN_THRESHOLDS)
