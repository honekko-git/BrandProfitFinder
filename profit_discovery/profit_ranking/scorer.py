"""Scoring helpers for used luxury profit ranking."""

from __future__ import annotations

from profit_discovery.brand_catalog.catalog import DEFAULT_OPPORTUNITY_PROFILES
from profit_discovery.config.used_luxury import (
    USED_LUXURY_A_TIER_BRANDS,
    USED_LUXURY_B_TIER_BRANDS,
    USED_LUXURY_S_TIER_BRANDS,
    UsedLuxuryModeConfig,
)
from profit_discovery.discovery_runner.models import DiscoveryCandidateResult, DiscoveryCandidateStatus
from profit_discovery.opportunity.scorer import OpportunityScorer
from profit_discovery.profit_ranking.models import UsedLuxuryProfitScore
from profit_intelligence.demand.models import SalesDemandProfile
from profit_intelligence.normalization import clamp_score, piecewise_linear_score

WEIGHT_PROFIT = 0.35
WEIGHT_DEMAND = 0.30
WEIGHT_TURNOVER = 0.20
WEIGHT_RISK = 0.15

TIER_DEFAULT_RISK: dict[str, float] = {
    "S": 20.0,
    "A": 30.0,
    "B": 38.0,
}

SOLD_COUNT_TURNOVER_THRESHOLDS: tuple[tuple[float, float], ...] = (
    (0.0, 0.0),
    (5.0, 35.0),
    (10.0, 55.0),
    (20.0, 75.0),
    (50.0, 90.0),
    (100.0, 100.0),
)


class UsedLuxuryProfitScorer:
    """Compute used-luxury profit ranking scores from discovery candidates."""

    def __init__(
        self,
        *,
        config: UsedLuxuryModeConfig | None = None,
        base_scorer: OpportunityScorer | None = None,
    ) -> None:
        self._config = config or UsedLuxuryModeConfig.default()
        self._base_scorer = base_scorer or OpportunityScorer()
        self._brand_risk = {
            profile.name.lower(): profile.risk_score
            for profile in DEFAULT_OPPORTUNITY_PROFILES
        }

    def score(
        self,
        candidate: DiscoveryCandidateResult,
        demand_profile: SalesDemandProfile | None,
    ) -> UsedLuxuryProfitScore:
        """Build one used luxury profit score."""
        base_score = self._base_scorer.score(candidate)
        profit_score = base_score.profit_score
        demand_score = _resolve_demand_score(demand_profile)
        turnover_score = _score_turnover(demand_profile)
        risk_score = self._score_risk(candidate)

        total_score = clamp_score(
            profit_score * WEIGHT_PROFIT
            + demand_score * WEIGHT_DEMAND
            + turnover_score * WEIGHT_TURNOVER
            + risk_score * WEIGHT_RISK
        )

        return UsedLuxuryProfitScore(
            profit_score=profit_score,
            demand_score=demand_score,
            turnover_score=turnover_score,
            risk_score=risk_score,
            total_score=total_score,
        )

    def _score_risk(self, candidate: DiscoveryCandidateResult) -> float:
        """Return a higher score when purchase risk is lower."""
        brand = candidate.supplier_product.brand.strip()
        raw_risk = self._brand_risk.get(brand.lower(), self._default_tier_risk(brand))
        inverse_risk = clamp_score(100.0 - raw_risk)

        inventory_risk = _resolve_inventory_risk(candidate)
        if inventory_risk is not None:
            inverse_risk = clamp_score(inverse_risk * 0.7 + (100.0 - inventory_risk) * 0.3)

        market_confidence = _resolve_market_confidence(candidate)
        return clamp_score(inverse_risk * 0.75 + market_confidence * 0.25)

    def _default_tier_risk(self, brand: str) -> float:
        normalized = brand.strip().lower()
        if normalized in {name.lower() for name in USED_LUXURY_S_TIER_BRANDS}:
            return TIER_DEFAULT_RISK["S"]
        if normalized in {name.lower() for name in USED_LUXURY_A_TIER_BRANDS}:
            return TIER_DEFAULT_RISK["A"]
        if normalized in {name.lower() for name in USED_LUXURY_B_TIER_BRANDS}:
            return TIER_DEFAULT_RISK["B"]
        return TIER_DEFAULT_RISK["B"]


def _resolve_demand_score(demand_profile: SalesDemandProfile | None) -> float:
    if demand_profile is None:
        return 0.0
    return clamp_score(demand_profile.demand_score)


def _score_turnover(demand_profile: SalesDemandProfile | None) -> float:
    if demand_profile is None:
        return 0.0

    sold_component = piecewise_linear_score(
        float(demand_profile.sold_count),
        SOLD_COUNT_TURNOVER_THRESHOLDS,
    )
    sell_through_component = clamp_score(demand_profile.sell_through_rate * 100.0)
    return clamp_score(sold_component * 0.55 + sell_through_component * 0.45)


def _resolve_inventory_risk(candidate: DiscoveryCandidateResult) -> float | None:
    if candidate.status is not DiscoveryCandidateStatus.SUCCESS:
        return None
    if candidate.profit_result is None:
        return None
    raw = candidate.profit_result.metadata.get("inventory_risk_score")
    if raw is None:
        return None
    try:
        return clamp_score(float(raw))
    except (TypeError, ValueError):
        return None


def _resolve_market_confidence(candidate: DiscoveryCandidateResult) -> float:
    market_evaluation = candidate.market_evaluation
    if market_evaluation is None:
        return 0.0
    confidence = market_evaluation.confidence_score
    if confidence <= 1.0:
        return clamp_score(confidence * 100.0)
    return clamp_score(confidence)
