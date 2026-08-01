"""Yahoo Auction live domestic market exceptions."""


class YahooAuctionTransportError(RuntimeError):
    """Raised when Yahoo Auction HTTP transport fails."""


class YahooAuctionAuthenticationError(YahooAuctionTransportError):
    """Raised when Yahoo Auction HTTP authentication fails."""


class YahooAuctionResponseError(YahooAuctionTransportError):
    """Raised when Yahoo Auction HTTP response validation fails."""


class YahooAuctionLiveUnavailableError(RuntimeError):
    """Raised when Yahoo Auction live data is unavailable or not configured."""
