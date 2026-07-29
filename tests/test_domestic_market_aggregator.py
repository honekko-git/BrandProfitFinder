"""Tests for domestic market aggregator."""

from __future__ import annotations

from marketplace.domestic_market import (
    DomesticMarketAggregator,
    DomesticMarketSource,
    FakeMercariDomesticMarketClient,
    YahooAuctionDomesticMarketClient,
    merge_market_prices,
)
from marketplace.domestic_market.models import DomesticMarketPriceSnapshot
from marketplace.yahoo_auction.client import FakeYahooAuctionClient


def _yahoo_source() -> tuple[DomesticMarketSource, YahooAuctionDomesticMarketClient]:
    return (
        DomesticMarketSource(name="yahoo_auction", enabled=True),
        YahooAuctionDomesticMarketClient(FakeYahooAuctionClient()),
    )


def test_aggregator_yahoo_auction_only_success() -> None:
    aggregator = DomesticMarketAggregator(clients=[_yahoo_source()])

    result = aggregator.aggregate("chanel wallet", max_results=20)

    assert result.average_price_jpy == 160000.0
    assert result.median_price_jpy == 160000.0
    assert result.confidence_score == 0.6
    assert result.sources == ("yahoo_auction",)


def test_aggregator_merges_multiple_clients() -> None:
    aggregator = DomesticMarketAggregator(
        clients=[
            _yahoo_source(),
            (
                DomesticMarketSource(name="mercari", enabled=True),
                FakeMercariDomesticMarketClient([150000, 170000]),
            ),
        ]
    )

    result = aggregator.aggregate("chanel wallet", max_results=20)

    assert result.sources == ("yahoo_auction", "mercari")
    assert len(result.snapshots) == 2
    assert result.metadata["sample_count"] == 7
    assert result.average_price_jpy == round((160000 * 5 + 150000 + 170000) / 7, 10)


def test_aggregator_continues_when_one_client_fails() -> None:
    aggregator = DomesticMarketAggregator(
        clients=[
            _yahoo_source(),
            (
                DomesticMarketSource(name="mercari", enabled=True),
                FakeMercariDomesticMarketClient(should_fail=True),
            ),
        ]
    )

    result = aggregator.aggregate("chanel wallet", max_results=20)

    assert result.sources == ("yahoo_auction",)
    assert result.average_price_jpy == 160000.0
    assert "errors" in result.metadata


def test_merge_market_prices_confidence_thresholds() -> None:
    snapshots = [
        DomesticMarketPriceSnapshot(
            source="yahoo_auction",
            prices=tuple([100000] * 5),
            average_price_jpy=100000.0,
            median_price_jpy=100000.0,
            confidence_score=0.6,
        )
    ]

    result = merge_market_prices(snapshots)

    assert result.confidence_score == 0.6


def test_aggregator_handles_empty_results() -> None:
    aggregator = DomesticMarketAggregator(
        clients=[
            (
                DomesticMarketSource(name="mercari", enabled=True),
                FakeMercariDomesticMarketClient([]),
            ),
        ]
    )

    result = aggregator.aggregate("unknown product", max_results=20)

    assert result.average_price_jpy == 0.0
    assert result.confidence_score == 0.0
    assert result.sources == ()
