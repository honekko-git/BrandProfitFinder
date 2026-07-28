"""
Amazon.co.jp marketplace exceptions.
"""


class AmazonMarketplaceError(Exception):
    """Base exception for Amazon marketplace failures."""


class AmazonConfigurationError(AmazonMarketplaceError):
    """Raised when Amazon marketplace configuration is missing or invalid."""


class AmazonResponseParseError(AmazonMarketplaceError):
    """Raised when Amazon response payload cannot be parsed."""
