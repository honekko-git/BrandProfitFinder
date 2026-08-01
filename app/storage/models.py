"""SQLite storage models for saved opportunities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class OpportunityStatus(StrEnum):
    """Workflow status for a saved opportunity."""

    NEW = "NEW"
    WATCHING = "WATCHING"
    PURCHASED = "PURCHASED"
    SKIPPED = "SKIPPED"


@dataclass(slots=True)
class OpportunityRecord:
    """Persisted used-luxury opportunity candidate."""

    id: int | None
    product_name: str
    brand: str
    category: str
    purchase_source: str
    purchase_url: str
    purchase_price: float
    selling_market: str
    selling_url: str
    selling_price: float
    estimated_profit: float
    profit_margin: float
    demand_score: float
    turnover_score: float
    arbitrage_score: float
    decision: str
    status: OpportunityStatus
    created_at: datetime
    updated_at: datetime
