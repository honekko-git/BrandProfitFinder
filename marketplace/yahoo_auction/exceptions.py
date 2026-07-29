"""Yahoo Auction domestic market exceptions."""

from __future__ import annotations


class YahooAuctionError(Exception):
    """Base exception for Yahoo Auction domestic market failures."""


class YahooAuctionConfigError(YahooAuctionError):
    """Raised when Yahoo Auction configuration is missing or invalid."""


class YahooAuctionDataError(YahooAuctionError):
    """Raised when fixture or response data is invalid."""


class YahooAuctionParseError(YahooAuctionError):
    """Raised when sold listing data cannot be parsed."""
