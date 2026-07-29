"""Domestic market price merge helpers."""

from __future__ import annotations

from statistics import median

from marketplace.domestic_market.models import (
    DomesticMarketAggregateResult,
    DomesticMarketPriceSnapshot,
)


def merge_market_prices(
    snapshots: list[DomesticMarketPriceSnapshot],
) -> DomesticMarketAggregateResult:
    """Merge multiple domestic market snapshots into one aggregate result."""
    combined_prices = [price for snapshot in snapshots for price in snapshot.prices]
    sources = tuple(snapshot.source for snapshot in snapshots)

    if not combined_prices:
        return DomesticMarketAggregateResult(
            average_price_jpy=0.0,
            median_price_jpy=0.0,
            confidence_score=0.0,
            sources=sources,
            snapshots=tuple(snapshots),
            metadata={"sample_count": 0},
        )

    return DomesticMarketAggregateResult(
        average_price_jpy=sum(combined_prices) / len(combined_prices),
        median_price_jpy=float(median(combined_prices)),
        confidence_score=_confidence_score(len(combined_prices)),
        sources=sources,
        snapshots=tuple(snapshots),
        metadata={"sample_count": len(combined_prices)},
    )


def snapshot_from_prices(
    source: str,
    prices: list[int],
    *,
    metadata: dict[str, object] | None = None,
) -> DomesticMarketPriceSnapshot | None:
    """Build one market snapshot from sold prices."""
    if not prices:
        return None

    return DomesticMarketPriceSnapshot(
        source=source,
        prices=tuple(prices),
        average_price_jpy=sum(prices) / len(prices),
        median_price_jpy=float(median(prices)),
        confidence_score=_confidence_score(len(prices)),
        metadata=dict(metadata or {}),
    )


def _confidence_score(sample_count: int) -> float:
    if sample_count >= 20:
        return 1.0
    if sample_count >= 10:
        return 0.8
    if sample_count >= 5:
        return 0.6
    return 0.3
