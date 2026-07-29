"""Ranking helpers for opportunity results."""

from __future__ import annotations

from profit_discovery.opportunity.models import OpportunityResult


def rank_opportunities(opportunities: list[OpportunityResult]) -> list[OpportunityResult]:
    """Rank opportunity results by total score descending."""
    ranked = sorted(opportunities, key=_rank_key)
    return [
        OpportunityResult(
            candidate=item.candidate,
            score=item.score,
            recommendation_rank=index,
        )
        for index, item in enumerate(ranked, start=1)
    ]


def _rank_key(item: OpportunityResult) -> tuple[float, float, float, float, str]:
    score = item.score
    supplier_id = item.candidate.supplier_product.external_id
    return (
        -score.total_score,
        -score.profit_score,
        -score.margin_score,
        -score.roi_score,
        supplier_id,
    )
