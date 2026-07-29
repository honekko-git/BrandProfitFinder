"""Opportunity ranking models for purchase-priority scoring."""

from __future__ import annotations

from dataclasses import dataclass

from profit_discovery.discovery_runner.models import DiscoveryCandidateResult
from profit_intelligence.demand.models import SalesDemandProfile


@dataclass(frozen=True, slots=True)
class OpportunityScore:
    """Weighted purchase-priority score derived from discovery evaluation."""

    profit_score: float
    margin_score: float
    roi_score: float
    market_confidence_score: float
    supplier_score: float
    total_score: float


@dataclass(frozen=True, slots=True)
class OpportunityResult:
    """One discovery candidate paired with its opportunity score and rank."""

    candidate: DiscoveryCandidateResult
    score: OpportunityScore
    recommendation_rank: int | None = None


@dataclass(frozen=True, slots=True)
class DemandIntegratedOpportunityScore:
    """Opportunity score extended with sales demand weighting."""

    profit_score: float
    margin_score: float
    roi_score: float
    market_confidence_score: float
    supplier_score: float
    demand_score: float
    total_score: float


@dataclass(frozen=True, slots=True)
class DemandIntegratedOpportunityResult:
    """One discovery candidate paired with demand-integrated scoring."""

    candidate: DiscoveryCandidateResult
    demand_profile: SalesDemandProfile | None
    score: DemandIntegratedOpportunityScore
    recommendation_rank: int | None = None
