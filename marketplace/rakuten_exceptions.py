"""
Rakuten Ichiba marketplace exceptions.
"""


class RakutenMarketplaceError(Exception):
    """Base exception for Rakuten marketplace failures."""


class RakutenConfigError(RakutenMarketplaceError):
    """Raised when Rakuten API configuration is missing or invalid."""


class RakutenApiError(RakutenMarketplaceError):
    """Base exception for Rakuten API HTTP failures."""


class RakutenClientError(RakutenApiError):
    """Raised for HTTP 400 responses."""


class RakutenNotFoundError(RakutenApiError):
    """Raised for HTTP 404 responses."""


class RakutenRateLimitError(RakutenApiError):
    """Raised for HTTP 429 responses."""


class RakutenServerError(RakutenApiError):
    """Raised for HTTP 500 responses."""


class RakutenServiceUnavailableError(RakutenApiError):
    """Raised for HTTP 503 responses."""


class RakutenResponseError(RakutenApiError):
    """Raised when response body is not valid JSON."""
