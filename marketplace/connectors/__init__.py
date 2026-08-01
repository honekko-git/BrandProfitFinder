"""Interchangeable market data connectors."""

from marketplace.connectors.base import MarketConnector, MarketConnectorUnavailableError
from marketplace.connectors.config import MarketConnectorConfig
from marketplace.connectors.execution import MarketConnectorExecutionResult
from marketplace.connectors.fixtures import FixtureMarketConnector, SUPPORTED_MARKETS
from marketplace.connectors.live import (
    FashionphileLiveConnector,
    FallbackMarketConnector,
    MarketHttpClient,
    MercariLiveConnector,
    YahooAuctionLiveConnector,
)
from marketplace.connectors.models import MarketListing
from marketplace.connectors.resolver import (
    MarketConnectorResolution,
    MarketConnectorResolver,
    MarketConnectorSourceMode,
)

__all__ = [
    "FashionphileLiveConnector",
    "FallbackMarketConnector",
    "FixtureMarketConnector",
    "MarketConnector",
    "MarketConnectorConfig",
    "MarketConnectorExecutionResult",
    "MarketConnectorResolution",
    "MarketConnectorResolver",
    "MarketConnectorSourceMode",
    "MarketConnectorUnavailableError",
    "MarketHttpClient",
    "MarketListing",
    "MercariLiveConnector",
    "SUPPORTED_MARKETS",
    "YahooAuctionLiveConnector",
]
