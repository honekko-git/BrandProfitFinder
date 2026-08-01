"""Yahoo Auction live domestic market models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class YahooAuctionLiveResponse:
    """Normalized live sold-price response from Yahoo Auction."""

    query: str
    items: tuple[int, ...]
    average_price: float
    sold_count: int
    source: str
    retrieved_at: str
