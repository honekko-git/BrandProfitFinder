"""
Grailed marketplace exceptions.
"""


class GrailedError(Exception):
    """Base exception for Grailed marketplace failures."""


class GrailedConfigurationError(GrailedError):
    """Raised when Grailed configuration or client is missing."""


class GrailedClientError(GrailedError):
    """Raised when Grailed client operations fail."""


class GrailedResponseError(GrailedError):
    """Raised when Grailed response payload structure is invalid."""


class GrailedParseError(GrailedError):
    """Raised when Grailed item data cannot be parsed."""
