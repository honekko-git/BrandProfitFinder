"""Domestic market aggregation foundation."""

from marketplace.domestic_market.adapter import merge_market_prices, snapshot_from_prices
from marketplace.domestic_market.aggregator import DomesticMarketAggregator
from marketplace.domestic_market.base import DomesticMarketClient
from marketplace.domestic_market.clients import (
    DomesticMarketClientResolution,
    DomesticMarketClientResolver,
    DomesticMarketSourceMode,
    FakeMercariDomesticMarketClient,
    RakumaDomesticMarketClient,
    YahooAuctionDomesticMarketClient,
)
from marketplace.domestic_market.config import DomesticMarketRuntimeConfig
from marketplace.domestic_market.execution import (
    ExecutionTrackingDomesticMarketClient,
    MarketExecutionResult,
    read_market_execution,
    requested_mode_from_config,
    resolve_actual_source,
    resolve_client_name,
    wrap_with_execution_tracking,
)
from marketplace.domestic_market.models import (
    DomesticMarketAggregateResult,
    DomesticMarketPriceSnapshot,
    DomesticMarketSource,
)
from marketplace.domestic_market.yahoo_auction import (
    FakeYahooAuctionTransport,
    TransportMode,
    YahooAuctionAuthenticationError,
    YahooAuctionFallbackDomesticMarketClient,
    YahooAuctionHTTPTransport,
    YahooAuctionLiveDomesticMarketClient,
    YahooAuctionLiveResponse,
    YahooAuctionLiveUnavailableError,
    YahooAuctionResponseError,
    YahooAuctionTransport,
    YahooAuctionTransportError,
)

__all__ = [
    "DomesticMarketAggregateResult",
    "DomesticMarketAggregator",
    "DomesticMarketClient",
    "DomesticMarketClientResolution",
    "DomesticMarketClientResolver",
    "DomesticMarketPriceSnapshot",
    "DomesticMarketRuntimeConfig",
    "DomesticMarketSource",
    "DomesticMarketSourceMode",
    "ExecutionTrackingDomesticMarketClient",
    "FakeMercariDomesticMarketClient",
    "FakeYahooAuctionTransport",
    "MarketExecutionResult",
    "RakumaDomesticMarketClient",
    "TransportMode",
    "YahooAuctionAuthenticationError",
    "YahooAuctionDomesticMarketClient",
    "YahooAuctionFallbackDomesticMarketClient",
    "YahooAuctionHTTPTransport",
    "YahooAuctionLiveDomesticMarketClient",
    "YahooAuctionLiveResponse",
    "YahooAuctionLiveUnavailableError",
    "YahooAuctionResponseError",
    "YahooAuctionTransport",
    "YahooAuctionTransportError",
    "merge_market_prices",
    "read_market_execution",
    "requested_mode_from_config",
    "resolve_actual_source",
    "resolve_client_name",
    "snapshot_from_prices",
    "wrap_with_execution_tracking",
]
