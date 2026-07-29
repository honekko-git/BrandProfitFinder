"""Common marketplace transport exceptions for Version 2."""

from __future__ import annotations


class MarketplaceTransportError(Exception):
    """Base exception for shared marketplace HTTP transport failures."""

    def __init__(
        self,
        message: str,
        *,
        marketplace_name: str | None = None,
        status_code: int | None = None,
        retry_count: int = 0,
    ) -> None:
        super().__init__(message)
        self.marketplace_name = marketplace_name
        self.status_code = status_code
        self.retry_count = retry_count


class MarketplaceConnectionError(MarketplaceTransportError):
    """Raised when a connection to the marketplace cannot be established."""


class MarketplaceTimeoutError(MarketplaceTransportError):
    """Raised when a marketplace request exceeds the configured timeout."""


class MarketplaceRateLimitError(MarketplaceTransportError):
    """Raised when marketplace rate limits persist after retries."""


class MarketplaceAuthenticationError(MarketplaceTransportError):
    """Raised for HTTP 401/403 authentication or authorization failures."""
