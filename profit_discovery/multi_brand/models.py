"""Multi-brand discovery models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from profit_discovery.category_catalog.models import BrandCategorySearchTarget
from profit_discovery.discovery_runner.models import BatchDiscoveryResult, DiscoveryCandidateResult
from profit_discovery.opportunity.models import DemandIntegratedOpportunityResult, OpportunityResult


@dataclass(frozen=True, slots=True)
class MultiBrandDiscoveryRequest:
    """Input for running discovery across multiple brands."""

    brands: list[str]
    category: str | None = None
    keyword: str | None = None
    max_results_per_brand: int = 20
    search_targets: tuple[BrandCategorySearchTarget, ...] | None = None


@dataclass(frozen=True, slots=True)
class BrandDiscoveryResult:
    """Evaluation output for one brand."""

    brand: str
    batch_result: BatchDiscoveryResult | None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MultiBrandDiscoveryResult:
    """Aggregated multi-brand discovery output."""

    results: tuple[BrandDiscoveryResult, ...]
    ranked_candidates: tuple[DiscoveryCandidateResult, ...]
    ranked_opportunities: tuple[OpportunityResult, ...]
    successful_brands: tuple[str, ...]
    failed_brands: tuple[str, ...]
    total_candidates: int
    ranked_demand_opportunities: tuple[DemandIntegratedOpportunityResult, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
