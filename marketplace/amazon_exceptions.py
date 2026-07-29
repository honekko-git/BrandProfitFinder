"""
Amazon.co.jp marketplace exceptions.
"""


class AmazonMarketplaceError(Exception):
    """Base exception for Amazon marketplace failures."""


class AmazonConfigurationError(AmazonMarketplaceError):
    """Raised when Amazon marketplace configuration is missing or invalid."""


class AmazonResponseParseError(AmazonMarketplaceError):
    """Raised when Amazon response payload cannot be parsed."""


class AmazonApiError(AmazonMarketplaceError):
    """Base exception for Amazon API HTTP failures."""


class AmazonAuthenticationError(AmazonApiError):
    """Raised for HTTP 401/403 authentication failures."""


class AmazonRateLimitError(AmazonApiError):
    """Raised for HTTP 429 rate limit responses."""


class AmazonClientError(AmazonApiError):
    """Raised for HTTP 4xx client errors."""


class AmazonServerError(AmazonApiError):
    """Raised for HTTP 5xx server errors."""
