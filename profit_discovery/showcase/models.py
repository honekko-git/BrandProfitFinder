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
