"""Demand-integrated opportunity scoring."""

from __future__ import annotations

from profit_discovery.discovery_runner.models import DiscoveryCandidateResult
from profit_discovery.opportunity.models import (
    DemandIntegratedOpportunityResult,
    DemandIntegratedOpportunityScore,
)
from profit_discovery.opportunity.scorer import OpportunityScorer
from profit_intelligence.demand.models import SalesDemandProfile
from profit_intelligence.normalization import clamp_score

WEIGHT_PROFIT = 0.25
WEIGHT_MARGIN = 0.15
WEIGHT_ROI = 0.15
WEIGHT_MARKET_CONFIDENCE = 0.15
WEIGHT_SUPPLIER = 0.10
WEIGHT_DEMAND = 0.20


class DemandIntegratedOpportunityScorer:
    """Build demand-aware opportunity scores without modifying OpportunityScorer."""

    def __init__(self, *, base_scorer: OpportunityScorer | None = None) -> None:
        self._base_scorer = base_scorer or OpportunityScorer()

    def score(
        self,
        candidate: DiscoveryCandidateResult,
        demand_profile: SalesDemandProfile | None,
    ) -> DemandIntegratedOpportunityScore:
        """Combine base opportunity components with demand scoring."""
        base_score = self._base_scorer.score(candidate)
        demand_score = _resolve_demand_score(demand_profile)

        total_score = clamp_score(
            base_score.profit_score * WEIGHT_PROFIT
            + base_score.margin_score * WEIGHT_MARGIN
            + base_score.roi_score * WEIGHT_ROI
            + base_score.market_confidence_score * WEIGHT_MARKET_CONFIDENCE
            + base_score.supplier_score * WEIGHT_SUPPLIER
            + demand_score * WEIGHT_DEMAND
        )

        return DemandIntegratedOpportunityScore(
            profit_score=base_score.profit_score,
            margin_score=base_score.margin_score,
            roi_score=base_score.roi_score,
            market_confidence_score=base_score.market_confidence_score,
            supplier_score=base_score.supplier_score,
            demand_score=demand_score,
            total_score=total_score,
        )

    def evaluate(
        self,
        candidate: DiscoveryCandidateResult,
        demand_profile: SalesDemandProfile | None,
    ) -> DemandIntegratedOpportunityResult:
        """Build one demand-integrated opportunity result."""
        return DemandIntegratedOpportunityResult(
            candidate=candidate,
            demand_profile=demand_profile,
            score=self.score(candidate, demand_profile),
        )


def _resolve_demand_score(demand_profile: SalesDemandProfile | None) -> float:
    if demand_profile is None:
        return 0.0
    return clamp_score(demand_profile.demand_score)
