"""Brand catalog models for automated discovery targeting."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class BrandTier(StrEnum):
    """Brand priority tier for automated discovery."""

    S = "S"
    A = "A"
    B = "B"


class BrandCapitalLevel(StrEnum):
    """Capital requirement level for brand inventory."""

    HIGH = "HIGH"
    A = "A"
    B = "B"


@dataclass(frozen=True, slots=True)
class BrandProfile:
    """One discoverable brand entry in the catalog."""

    name: str
    tier: str
    categories: tuple[str, ...] = ()
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class BrandOpportunityProfile:
    """Profit and demand profile for one discoverable brand."""

    name: str
    profit_score: float
    demand_score: float
    turnover_score: float
    risk_score: float
    capital_level: str
    enabled: bool = True

    def calculate_opportunity_score(self) -> float:
        """Calculate weighted opportunity score on a 0-100 scale."""
        risk_inverse = max(0.0, min(100.0, 100.0 - self.risk_score))
        score = (
            _clamp_score(self.profit_score) * 0.30
            + _clamp_score(self.demand_score) * 0.30
            + _clamp_score(self.turnover_score) * 0.20
            + risk_inverse * 0.20
        )
        return round(_clamp_score(score), 2)


def _clamp_score(value: float) -> float:
    return max(0.0, min(100.0, value))

