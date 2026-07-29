"""Automatic demand linking pipeline for discovery candidates."""

from __future__ import annotations

from profit_discovery.discovery_runner.models import DiscoveryCandidateResult, DiscoveryCandidateStatus
from profit_discovery.opportunity.demand_ranking import rank_demand_integrated_opportunities
from profit_discovery.opportunity.demand_scorer import DemandIntegratedOpportunityScorer
from profit_discovery.opportunity.models import DemandIntegratedOpportunityResult
from profit_intelligence.demand.lookup import DemandLookup
from profit_intelligence.demand.resolver import DemandQueryResolver


def build_auto_demand_integrated_ranking(
    candidates: list[DiscoveryCandidateResult] | tuple[DiscoveryCandidateResult, ...],
    *,
    resolver: DemandQueryResolver | None = None,
    lookup: DemandLookup | None = None,
    scorer: DemandIntegratedOpportunityScorer | None = None,
) -> list[DemandIntegratedOpportunityResult]:
    """Build and rank demand-integrated opportunities from discovery candidates."""
    active_resolver = resolver or DemandQueryResolver()
    active_lookup = lookup or DemandLookup()
    active_scorer = scorer or DemandIntegratedOpportunityScorer()

    opportunities: list[DemandIntegratedOpportunityResult] = []
    for candidate in candidates:
        if candidate.status is not DiscoveryCandidateStatus.SUCCESS:
            continue
        demand_query = active_resolver.resolve(candidate)
        demand_profile = active_lookup.find(demand_query.normalized_query)
        opportunities.append(active_scorer.evaluate(candidate, demand_profile))

    return rank_demand_integrated_opportunities(opportunities)
