"""
GOAT marketplace exceptions.
"""


class GoatError(Exception):
    """Base exception for GOAT marketplace failures."""


class GoatConfigurationError(GoatError):
    """Raised when GOAT configuration or client is missing."""


class GoatClientError(GoatError):
    """Raised when GOAT client operations fail."""


class GoatResponseError(GoatError):
    """Raised when GOAT response payload structure is invalid."""


class GoatParseError(GoatError):
    """Raised when GOAT item data cannot be parsed."""
