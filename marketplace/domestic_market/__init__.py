"""Domestic market aggregation foundation."""

from marketplace.domestic_market.adapter import merge_market_prices, snapshot_from_prices
from marketplace.domestic_market.aggregator import DomesticMarketAggregator
from marketplace.domestic_market.base import DomesticMarketClient
from marketplace.domestic_market.clients import (
    FakeMercariDomesticMarketClient,
    RakumaDomesticMarketClient,
    YahooAuctionDomesticMarketClient,
)
from marketplace.domestic_market.models import (
    DomesticMarketAggregateResult,
    DomesticMarketPriceSnapshot,
    DomesticMarketSource,
)

__all__ = [
    "DomesticMarketAggregateResult",
    "DomesticMarketAggregator",
    "DomesticMarketClient",
    "DomesticMarketPriceSnapshot",
    "DomesticMarketSource",
    "FakeMercariDomesticMarketClient",
    "RakumaDomesticMarketClient",
    "YahooAuctionDomesticMarketClient",
    "merge_market_prices",
    "snapshot_from_prices",
]
