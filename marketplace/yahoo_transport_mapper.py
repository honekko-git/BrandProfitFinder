"""Map Version 2 transport exceptions to Yahoo Shopping marketplace exceptions."""

from __future__ import annotations

from marketplace.yahoo_exceptions import (
    YahooApiError,
    YahooClientError,
    YahooRateLimitError,
    YahooServerError,
)
from utils.transport.exceptions import (
    MarketplaceAuthenticationError,
    MarketplaceConnectionError,
    MarketplaceRateLimitError,
    MarketplaceTimeoutError,
    MarketplaceTransportError,
)


def map_transport_exception(exc: Exception) -> YahooApiError:
    """
    Translate a transport-layer exception into a Yahoo marketplace exception.

    Preserves existing Yahoo error handling contracts.
    """
    if isinstance(exc, MarketplaceRateLimitError):
        return YahooRateLimitError("Yahoo API rate limit exceeded")

    if isinstance(exc, MarketplaceAuthenticationError):
        status = exc.status_code or 0
        return YahooClientError(f"Yahoo API client error: HTTP {status}")

    if isinstance(exc, MarketplaceTimeoutError):
        return YahooApiError("Yahoo API request timed out")

    if isinstance(exc, MarketplaceConnectionError):
        return YahooApiError("Yahoo API connection error")

    if isinstance(exc, MarketplaceTransportError):
        return _map_transport_error(exc)

    if isinstance(exc, YahooApiError):
        return exc

    return YahooApiError(str(exc))


def _map_transport_error(exc: MarketplaceTransportError) -> YahooApiError:
    status = exc.status_code
    if status is not None and status >= 500:
        return YahooServerError(f"Yahoo API server error: HTTP {status}")
    if status is not None and status >= 400:
        return YahooClientError(f"Yahoo API client error: HTTP {status}")
    return YahooApiError(str(exc))
