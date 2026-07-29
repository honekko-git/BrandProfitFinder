"""Demand profile helpers for opportunity ranking integration."""

from __future__ import annotations

from profit_discovery.discovery_runner.models import DiscoveryCandidateResult, DiscoveryCandidateStatus
from profit_discovery.opportunity.demand_scorer import DemandIntegratedOpportunityScorer
from profit_discovery.opportunity.models import DemandIntegratedOpportunityResult
from profit_intelligence.demand import DemandAnalyzer, SalesDemandProfile


def analyze_demand_for_queries(
    queries: list[str],
    *,
    analyzer: DemandAnalyzer | None = None,
    sold_data_by_query: dict[str, dict[str, float | int]] | None = None,
) -> tuple[SalesDemandProfile, ...]:
    """Analyze demand profiles for discovery queries without changing opportunity scoring."""
    active_analyzer = analyzer or DemandAnalyzer()
    sold_data = sold_data_by_query or {}
    profiles: list[SalesDemandProfile] = []
    for query in queries:
        payload = sold_data.get(query)
        if payload is None:
            continue
        profiles.append(active_analyzer.analyze(query, payload))
    return tuple(profiles)


def build_demand_integrated_opportunities(
    candidates: list[DiscoveryCandidateResult] | tuple[DiscoveryCandidateResult, ...],
    *,
    demand_profiles_by_query: dict[str, SalesDemandProfile] | None = None,
    search_query_by_candidate: dict[str, str] | None = None,
    scorer: DemandIntegratedOpportunityScorer | None = None,
) -> list[DemandIntegratedOpportunityResult]:
    """Build demand-integrated opportunity results for discovery candidates."""
    active_scorer = scorer or DemandIntegratedOpportunityScorer()
    demand_by_query = demand_profiles_by_query or {}
    query_by_candidate = search_query_by_candidate or {}
    opportunities: list[DemandIntegratedOpportunityResult] = []

    for candidate in candidates:
        if candidate.status is not DiscoveryCandidateStatus.SUCCESS:
            continue
        external_id = candidate.supplier_product.external_id
        query = query_by_candidate.get(external_id)
        demand_profile = demand_by_query.get(query) if query else None
        opportunities.append(active_scorer.evaluate(candidate, demand_profile))

    return opportunities
