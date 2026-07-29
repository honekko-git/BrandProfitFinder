"""Yahoo Auction domestic market models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class YahooAuctionListing:
    """One domestic sold Yahoo Auction listing."""

    listing_id: str
    title: str
    price_jpy: int
    brand: str | None = None
    sold_date: str | None = None
    bid_count: int | None = None
    condition: str | None = None
    url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize listing fields."""
        return asdict(self)


@dataclass(slots=True)
class DomesticMarketPrice:
    """Normalized domestic selling price derived from sold listings."""

    product_keyword: str
    average_price_jpy: float
    median_price_jpy: float
    min_price_jpy: int
    max_price_jpy: int
    sample_count: int
    confidence_score: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize market price fields."""
        return asdict(self)
