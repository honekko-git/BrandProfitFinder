"""
Yahoo Auction marketplace exceptions.
"""


class YahooAuctionMarketplaceError(Exception):
    """Base exception for Yahoo Auction marketplace failures."""


class YahooAuctionConfigError(YahooAuctionMarketplaceError):
    """Raised when Yahoo Auction configuration is missing or invalid."""


class YahooAuctionResponseError(YahooAuctionMarketplaceError):
    """Raised when Yahoo Auction response payload cannot be parsed."""
