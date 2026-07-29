"""Identity-aware demand integration pipeline for discovery candidates."""

from __future__ import annotations

from product_identity.duplicate_resolver import DuplicateResolver
from product_identity.identity_resolver import ProductIdentityResolver
from profit_discovery.discovery_runner.models import DiscoveryCandidateResult
from profit_discovery.opportunity.auto_demand_pipeline import build_auto_demand_integrated_ranking
from profit_discovery.opportunity.models import DemandIntegratedOpportunityResult
from profit_intelligence.demand.lookup import DemandLookup
from profit_intelligence.demand.resolver import DemandQueryResolver
from profit_discovery.opportunity.demand_scorer import DemandIntegratedOpportunityScorer


def build_identity_demand_integrated_ranking(
    candidates: list[DiscoveryCandidateResult] | tuple[DiscoveryCandidateResult, ...],
    *,
    identity_resolver: ProductIdentityResolver | None = None,
    duplicate_resolver: DuplicateResolver | None = None,
    demand_resolver: DemandQueryResolver | None = None,
    lookup: DemandLookup | None = None,
    scorer: DemandIntegratedOpportunityScorer | None = None,
) -> list[DemandIntegratedOpportunityResult]:
    """Resolve identity, merge duplicates, then rank demand-integrated opportunities."""
    active_duplicate_resolver = duplicate_resolver or DuplicateResolver()
    merged_candidates = active_duplicate_resolver.merge_candidates(
        candidates,
        identity_resolver=identity_resolver,
    )
    return build_auto_demand_integrated_ranking(
        merged_candidates,
        resolver=demand_resolver,
        lookup=lookup,
        scorer=scorer,
    )
