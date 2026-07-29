"""Map Version 2 transport exceptions to Amazon marketplace exceptions."""

from __future__ import annotations

from marketplace.amazon_exceptions import (
    AmazonApiError,
    AmazonAuthenticationError,
    AmazonClientError,
    AmazonMarketplaceError,
    AmazonRateLimitError,
    AmazonServerError,
)
from utils.transport.exceptions import (
    MarketplaceAuthenticationError,
    MarketplaceConnectionError,
    MarketplaceRateLimitError,
    MarketplaceTimeoutError,
    MarketplaceTransportError,
)


def map_transport_exception(exc: Exception) -> AmazonMarketplaceError:
    """
    Translate a transport-layer exception into an Amazon marketplace exception.

    Preserves existing Amazon error handling contracts.
    """
    if isinstance(exc, MarketplaceRateLimitError):
        return AmazonRateLimitError("Amazon API rate limit exceeded")

    if isinstance(exc, MarketplaceAuthenticationError):
        status = exc.status_code or 0
        return AmazonAuthenticationError(f"Amazon API authentication failed: HTTP {status}")

    if isinstance(exc, MarketplaceTimeoutError):
        return AmazonApiError("Amazon API request timed out")

    if isinstance(exc, MarketplaceConnectionError):
        return AmazonApiError("Amazon API connection error")

    if isinstance(exc, MarketplaceTransportError):
        return _map_transport_error(exc)

    if isinstance(exc, AmazonMarketplaceError):
        return exc

    return AmazonApiError(str(exc))


def _map_transport_error(exc: MarketplaceTransportError) -> AmazonMarketplaceError:
    status = exc.status_code
    if status is not None and status >= 500:
        return AmazonServerError(f"Amazon API server error: HTTP {status}")
    if status is not None and status >= 400:
        return AmazonClientError(f"Amazon API client error: HTTP {status}")
    return AmazonApiError(str(exc))
