"""
Vestiaire Collective marketplace exceptions.
"""


class VestiaireError(Exception):
    """Base exception for Vestiaire marketplace failures."""


class VestiaireConfigurationError(VestiaireError):
    """Raised when Vestiaire configuration or client is missing."""


class VestiaireClientError(VestiaireError):
    """Raised when Vestiaire client operations fail."""


class VestiaireResponseError(VestiaireError):
    """Raised when Vestiaire response payload structure is invalid."""


class VestiaireParseError(VestiaireError):
    """Raised when Vestiaire item data cannot be parsed."""
