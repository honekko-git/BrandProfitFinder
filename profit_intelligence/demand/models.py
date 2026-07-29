"""Sales demand intelligence models."""

from __future__ import annotations

from dataclasses import dataclass

from profit_intelligence.normalization import clamp_score


@dataclass(frozen=True, slots=True)
class DemandQuery:
    """Normalized demand lookup query derived from a discovery candidate."""

    brand: str
    product_type: str
    normalized_query: str


@dataclass(frozen=True, slots=True)
class SalesDemandProfile:
    """Observed sales demand metrics for one search query."""

    query: str
    period_days: int
    sold_count: int
    average_sold_price_jpy: float
    sell_through_rate: float
    demand_score: float

    def calculate_demand_score(self) -> float:
        """Calculate demand score from sold volume and sell-through rate."""
        score = _sold_count_score(self.sold_count)
        score += _sell_through_adjustment(self.sell_through_rate)
        return clamp_score(score)


def _sold_count_score(sold_count: int) -> float:
    if sold_count >= 50:
        return clamp_score(90.0 + min(10.0, (sold_count - 50) / 50.0 * 10.0))
    if sold_count >= 20:
        return clamp_score(75.0 + (sold_count - 20) / 29.0 * 15.0)
    if sold_count >= 10:
        return clamp_score(50.0 + (sold_count - 10) / 9.0 * 25.0)
    if sold_count >= 5:
        return clamp_score(40.0 + (sold_count - 5) / 4.0 * 10.0)
    if sold_count <= 0:
        return 0.0
    return clamp_score(sold_count / 4.0 * 40.0)


def _sell_through_adjustment(sell_through_rate: float) -> float:
    if sell_through_rate >= 0.8:
        return 10.0
    if sell_through_rate >= 0.5:
        return 5.0
    return 0.0
