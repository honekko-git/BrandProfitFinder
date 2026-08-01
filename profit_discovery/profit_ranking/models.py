"""Models for used luxury profit ranking."""

from __future__ import annotations

from dataclasses import dataclass

from profit_discovery.discovery_runner.models import DiscoveryCandidateResult
from profit_intelligence.demand.models import SalesDemandProfile


@dataclass(frozen=True, slots=True)
class UsedLuxuryProfitScore:
    """Weighted purchase-priority score for used luxury products."""

    profit_score: float
    demand_score: float
    turnover_score: float
    risk_score: float
    total_score: float
    recommendation_rank: int | None = None


@dataclass(frozen=True, slots=True)
class UsedLuxuryProfitRankedResult:
    """One used luxury candidate paired with profit ranking scores."""

    candidate: DiscoveryCandidateResult
    demand_profile: SalesDemandProfile | None
    score: UsedLuxuryProfitScore
