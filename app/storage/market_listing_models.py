"""SQLite storage models for imported market listings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class MarketListingRecord:
    """Persisted imported market listing."""

    id: int | None
    title: str
    brand: str
    category: str
    condition: str
    price: float
    currency: str
    market_name: str
    url: str
    external_key: str
    created_at: datetime
