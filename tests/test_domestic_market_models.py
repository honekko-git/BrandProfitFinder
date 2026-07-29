"""Tests for domestic market aggregator models."""

from __future__ import annotations

from marketplace.domestic_market.models import (
    DomesticMarketAggregateResult,
    DomesticMarketPriceSnapshot,
    DomesticMarketSource,
)


def test_domestic_market_source_creation() -> None:
    source = DomesticMarketSource(name="yahoo_auction", enabled=True)

    assert source.name == "yahoo_auction"
    assert source.enabled is True


def test_domestic_market_price_snapshot_creation() -> None:
    snapshot = DomesticMarketPriceSnapshot(
        source="yahoo_auction",
        prices=(155000, 160000, 165000),
        average_price_jpy=160000.0,
        median_price_jpy=160000.0,
        confidence_score=0.3,
    )

    assert snapshot.source == "yahoo_auction"
    assert len(snapshot.prices) == 3


def test_domestic_market_aggregate_result_creation() -> None:
    snapshot = DomesticMarketPriceSnapshot(
        source="yahoo_auction",
        prices=(160000,),
        average_price_jpy=160000.0,
        median_price_jpy=160000.0,
        confidence_score=0.3,
    )
    result = DomesticMarketAggregateResult(
        average_price_jpy=160000.0,
        median_price_jpy=160000.0,
        confidence_score=0.3,
        sources=("yahoo_auction",),
        snapshots=(snapshot,),
    )

    assert result.average_price_jpy == 160000.0
    assert result.sources == ("yahoo_auction",)
