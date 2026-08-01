"""Market data connector models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class MarketListing:
    """Normalized market listing for connector interchange."""

    id: str
    title: str
    brand: str
    category: str
    condition: str
    price: Decimal
    currency: str
    market_name: str
    url: str
    source_type: str
    created_at: datetime
