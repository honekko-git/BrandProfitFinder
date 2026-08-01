"""Yahoo Auction live domestic market adapter foundation."""

from marketplace.domestic_market.yahoo_auction.config import TransportMode
from marketplace.domestic_market.yahoo_auction.exceptions import (
    YahooAuctionAuthenticationError,
    YahooAuctionLiveUnavailableError,
    YahooAuctionResponseError,
    YahooAuctionTransportError,
)
from marketplace.domestic_market.yahoo_auction.fallback_client import YahooAuctionFallbackDomesticMarketClient
from marketplace.domestic_market.yahoo_auction.http_transport import YahooAuctionHTTPTransport
from marketplace.domestic_market.yahoo_auction.live_client import YahooAuctionLiveDomesticMarketClient
from marketplace.domestic_market.yahoo_auction.models import YahooAuctionLiveResponse
from marketplace.domestic_market.yahoo_auction.parser import ParsedSoldItem, parse_sold_items, calculate_average_price, to_market_price_data
from marketplace.domestic_market.yahoo_auction.transport import FakeYahooAuctionTransport, YahooAuctionTransport

__all__ = [
    "FakeYahooAuctionTransport",
    "ParsedSoldItem",
    "TransportMode",
    "YahooAuctionAuthenticationError",
    "YahooAuctionFallbackDomesticMarketClient",
    "YahooAuctionHTTPTransport",
    "YahooAuctionLiveDomesticMarketClient",
    "YahooAuctionLiveResponse",
    "YahooAuctionLiveUnavailableError",
    "YahooAuctionResponseError",
    "YahooAuctionTransport",
    "YahooAuctionTransportError",
    "calculate_average_price",
    "parse_sold_items",
    "to_market_price_data",
]
