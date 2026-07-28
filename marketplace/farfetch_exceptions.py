"""
Farfetch marketplace exceptions.
"""


class FarfetchError(Exception):
    """Base exception for Farfetch marketplace failures."""


class FarfetchConfigurationError(FarfetchError):
    """Raised when Farfetch configuration or client is missing."""


class FarfetchClientError(FarfetchError):
    """Raised when Farfetch client operations fail."""


class FarfetchResponseError(FarfetchError):
    """Raised when Farfetch response payload structure is invalid."""


class FarfetchParseError(FarfetchError):
    """Raised when Farfetch item data cannot be parsed."""
