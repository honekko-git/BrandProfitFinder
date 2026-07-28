"""
Yahoo Shopping API exceptions.
"""


class YahooConfigError(Exception):
    """Raised when Yahoo API configuration is missing or invalid."""


class YahooApiError(Exception):
    """Base exception for Yahoo API failures."""


class YahooClientError(YahooApiError):
    """Raised for HTTP 4xx responses."""


class YahooRateLimitError(YahooApiError):
    """Raised for HTTP 429 responses."""


class YahooServerError(YahooApiError):
    """Raised for HTTP 5xx responses."""


class YahooResponseError(YahooApiError):
    """Raised when response body is not valid JSON."""
