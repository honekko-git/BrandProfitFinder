"""Runtime tests for multi-source domestic market aggregation."""

from __future__ import annotations

from marketplace.domestic_market import (
    DomesticMarketAggregator,
    DomesticMarketSource,
    FakeMercariDomesticMarketClient,
    RakumaDomesticMarketClient,
    YahooAuctionDomesticMarketClient,
)
from marketplace.yahoo_auction.client import FakeYahooAuctionClient


def _yahoo_source() -> tuple[DomesticMarketSource, YahooAuctionDomesticMarketClient]:
    return (
        DomesticMarketSource(name="yahoo_auction", enabled=True),
        YahooAuctionDomesticMarketClient(FakeYahooAuctionClient()),
    )


def test_multi_source_aggregator_merges_yahoo_and_mercari_fixtures() -> None:
    aggregator = DomesticMarketAggregator(
        clients=[
            _yahoo_source(),
            (
                DomesticMarketSource(name="mercari", enabled=True),
                FakeMercariDomesticMarketClient(),
            ),
        ],
    )

    result = aggregator.aggregate("chanel wallet", max_results=20)

    assert len(aggregator.clients) == 2
    assert result.sources == ("yahoo_auction", "mercari")
    assert result.metadata["sample_count"] == 8
    assert result.average_price_jpy > 0


def test_multi_source_aggregator_continues_when_rakuma_is_empty() -> None:
    aggregator = DomesticMarketAggregator(
        clients=[
            _yahoo_source(),
            (
                DomesticMarketSource(name="mercari", enabled=True),
                FakeMercariDomesticMarketClient(),
            ),
            (
                DomesticMarketSource(name="rakuma", enabled=True),
                RakumaDomesticMarketClient(),
            ),
        ],
    )

    result = aggregator.aggregate("chanel wallet", max_results=20)

    assert result.sources == ("yahoo_auction", "mercari")
    assert result.metadata["sample_count"] == 8
    assert result.average_price_jpy == 156875.0


def test_multi_source_aggregator_continues_when_one_client_fails() -> None:
    aggregator = DomesticMarketAggregator(
        clients=[
            _yahoo_source(),
            (
                DomesticMarketSource(name="mercari", enabled=True),
                FakeMercariDomesticMarketClient(should_fail=True),
            ),
            (
                DomesticMarketSource(name="rakuma", enabled=True),
                RakumaDomesticMarketClient(),
            ),
        ],
    )

    result = aggregator.aggregate("chanel wallet", max_results=20)

    assert result.sources == ("yahoo_auction",)
    assert result.average_price_jpy == 160000.0
    assert "errors" in result.metadata


def test_yahoo_only_aggregator_remains_compatible() -> None:
    aggregator = DomesticMarketAggregator(clients=[_yahoo_source()])

    result = aggregator.aggregate("chanel wallet", max_results=20)

    assert len(aggregator.clients) == 1
    assert result.sources == ("yahoo_auction",)
    assert result.average_price_jpy == 160000.0
