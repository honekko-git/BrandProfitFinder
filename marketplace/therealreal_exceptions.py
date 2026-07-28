"""
The RealReal marketplace exceptions.
"""


class TheRealRealError(Exception):
    """Base exception for The RealReal marketplace failures."""


class TheRealRealConfigurationError(TheRealRealError):
    """Raised when The RealReal configuration or client is missing."""


class TheRealRealClientError(TheRealRealError):
    """Raised when The RealReal client operations fail."""


class TheRealRealResponseError(TheRealRealError):
    """Raised when The RealReal response payload structure is invalid."""


class TheRealRealParseError(TheRealRealError):
    """Raised when The RealReal item data cannot be parsed."""
