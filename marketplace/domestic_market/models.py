"""Domestic market aggregator models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class DomesticMarketSource:
    """One domestic market price source configuration."""

    name: str
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class DomesticMarketPriceSnapshot:
    """Price snapshot from one domestic market source."""

    source: str
    prices: tuple[int, ...]
    average_price_jpy: float
    median_price_jpy: float
    confidence_score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DomesticMarketAggregateResult:
    """Aggregated domestic market price across multiple sources."""

    average_price_jpy: float
    median_price_jpy: float
    confidence_score: float
    sources: tuple[str, ...]
    snapshots: tuple[DomesticMarketPriceSnapshot, ...]
    metadata: dict[str, Any] = field(default_factory=dict)
