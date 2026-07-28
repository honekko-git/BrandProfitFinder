"""
Chrono24 marketplace exceptions.
"""


class Chrono24Error(Exception):
    """Base exception for Chrono24 marketplace failures."""


class Chrono24ConfigurationError(Chrono24Error):
    """Raised when Chrono24 configuration or client is missing."""


class Chrono24ClientError(Chrono24Error):
    """Raised when Chrono24 client operations fail."""


class Chrono24ResponseError(Chrono24Error):
    """Raised when Chrono24 response payload structure is invalid."""


class Chrono24ParseError(Chrono24Error):
    """Raised when Chrono24 item data cannot be parsed."""
