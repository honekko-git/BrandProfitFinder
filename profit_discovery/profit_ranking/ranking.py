"""Ranking helpers for used luxury profit scoring."""

from __future__ import annotations

from profit_discovery.config.used_luxury import UsedLuxuryModeConfig
from profit_discovery.discovery_runner.models import DiscoveryCandidateStatus
from profit_discovery.opportunity.models import DemandIntegratedOpportunityResult
from profit_discovery.profit_ranking.models import UsedLuxuryProfitRankedResult, UsedLuxuryProfitScore
from profit_discovery.profit_ranking.scorer import UsedLuxuryProfitScorer


def rank_used_luxury_products(
    opportunities: list[DemandIntegratedOpportunityResult]
    | tuple[DemandIntegratedOpportunityResult, ...],
    *,
    config: UsedLuxuryModeConfig | None = None,
    scorer: UsedLuxuryProfitScorer | None = None,
) -> list[UsedLuxuryProfitRankedResult]:
    """Rank used luxury products by profit, demand, turnover, and risk."""
    active_config = config or UsedLuxuryModeConfig.default()
    active_scorer = scorer or UsedLuxuryProfitScorer(config=active_config)
    allowed_brands = {brand.lower() for brand in active_config.all_brand_names()}

    ranked_items: list[UsedLuxuryProfitRankedResult] = []
    for item in opportunities:
        candidate = item.candidate
        if candidate.status is not DiscoveryCandidateStatus.SUCCESS:
            continue
        brand = candidate.supplier_product.brand.strip().lower()
        if brand not in allowed_brands:
            continue
        score = active_scorer.score(candidate, item.demand_profile)
        ranked_items.append(
            UsedLuxuryProfitRankedResult(
                candidate=candidate,
                demand_profile=item.demand_profile,
                score=score,
            )
        )

    ranked_items.sort(key=_rank_key)
    return [
        UsedLuxuryProfitRankedResult(
            candidate=item.candidate,
            demand_profile=item.demand_profile,
            score=UsedLuxuryProfitScore(
                profit_score=item.score.profit_score,
                demand_score=item.score.demand_score,
                turnover_score=item.score.turnover_score,
                risk_score=item.score.risk_score,
                total_score=item.score.total_score,
                recommendation_rank=index,
            ),
        )
        for index, item in enumerate(ranked_items, start=1)
    ]


def _rank_key(item: UsedLuxuryProfitRankedResult) -> tuple[float, float, float, float, str]:
    score = item.score
    supplier_id = item.candidate.supplier_product.external_id
    return (
        -score.total_score,
        -score.profit_score,
        -score.turnover_score,
        -score.demand_score,
        supplier_id,
    )
