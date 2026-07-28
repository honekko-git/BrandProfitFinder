"""
StockX marketplace exceptions.
"""


class StockXError(Exception):
    """Base exception for StockX marketplace failures."""


class StockXConfigurationError(StockXError):
    """Raised when StockX configuration or client is missing."""


class StockXClientError(StockXError):
    """Raised when StockX client operations fail."""


class StockXResponseError(StockXError):
    """Raised when StockX response payload structure is invalid."""


class StockXParseError(StockXError):
    """Raised when StockX item data cannot be parsed."""
