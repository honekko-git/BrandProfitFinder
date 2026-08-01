"""Showcase dashboard models for human-readable discovery results."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ShowcaseOpportunity:
    """One ranked opportunity prepared for showcase display."""

    rank: int
    product_name: str
    supplier: str
    profit_jpy: Decimal | None
    roi: Decimal | None
    demand_score: float
    opportunity_score: float
    decision: str
    category: str
    brand: str
    market_source: str = "Fixture"
    requested_market_mode: str = "FIXTURE"
    actual_market_source: str = "Fixture"
    fallback_used: bool = False
    business_mode: str = ""
    market_coverage: str = ""
    profit_rank: int | None = None
    turnover_score: float | None = None
    purchase_source: str = ""
    purchase_url: str = ""
    selling_market: str = ""
    selling_url: str = ""
    estimated_profit: Decimal | None = None
