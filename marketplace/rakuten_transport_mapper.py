"""Map Version 2 transport exceptions to Rakuten marketplace exceptions."""

from __future__ import annotations

from marketplace.rakuten_exceptions import (
    RakutenApiError,
    RakutenClientError,
    RakutenMarketplaceError,
    RakutenNotFoundError,
    RakutenRateLimitError,
    RakutenServerError,
    RakutenServiceUnavailableError,
)
from utils.transport.exceptions import (
    MarketplaceAuthenticationError,
    MarketplaceConnectionError,
    MarketplaceRateLimitError,
    MarketplaceTimeoutError,
    MarketplaceTransportError,
)


def map_transport_exception(exc: Exception) -> RakutenMarketplaceError:
    """
    Translate a transport-layer exception into a Rakuten marketplace exception.

    Preserves existing RakutenMarketplace error handling contracts.
    """
    if isinstance(exc, MarketplaceRateLimitError):
        return RakutenRateLimitError("Rakuten API rate limit exceeded")

    if isinstance(exc, MarketplaceAuthenticationError):
        status = exc.status_code or 0
        return RakutenApiError(f"Rakuten API error: HTTP {status}")

    if isinstance(exc, MarketplaceTimeoutError):
        return RakutenApiError("Rakuten API request timed out")

    if isinstance(exc, MarketplaceConnectionError):
        return RakutenApiError("Rakuten API connection error")

    if isinstance(exc, MarketplaceTransportError):
        return _map_transport_error(exc)

    if isinstance(exc, RakutenMarketplaceError):
        return exc

    return RakutenApiError(str(exc))


def _map_transport_error(exc: MarketplaceTransportError) -> RakutenMarketplaceError:
    status = exc.status_code
    if status == 404:
        return RakutenNotFoundError("Rakuten API returned no results")
    if status == 400:
        return RakutenClientError("Rakuten API parameter error")
    if status == 503:
        return RakutenServiceUnavailableError("Rakuten API service unavailable")
    if status is not None and status >= 500:
        return RakutenServerError(f"Rakuten API server error: HTTP {status}")
    if status is not None and status >= 400:
        return RakutenApiError(f"Rakuten API error: HTTP {status}")
    return RakutenApiError(str(exc))
