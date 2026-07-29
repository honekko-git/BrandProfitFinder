"""Ranking helpers for demand-integrated opportunity results."""

from __future__ import annotations

from profit_discovery.opportunity.models import DemandIntegratedOpportunityResult


def rank_demand_integrated_opportunities(
    opportunities: list[DemandIntegratedOpportunityResult],
) -> list[DemandIntegratedOpportunityResult]:
    """Rank demand-integrated opportunities by total score descending."""
    ranked = sorted(opportunities, key=_rank_key)
    return [
        DemandIntegratedOpportunityResult(
            candidate=item.candidate,
            demand_profile=item.demand_profile,
            score=item.score,
            recommendation_rank=index,
        )
        for index, item in enumerate(ranked, start=1)
    ]


def _rank_key(item: DemandIntegratedOpportunityResult) -> tuple[float, float, float, float, str]:
    score = item.score
    supplier_id = item.candidate.supplier_product.external_id
    return (
        -score.total_score,
        -score.demand_score,
        -score.profit_score,
        -score.roi_score,
        supplier_id,
    )
