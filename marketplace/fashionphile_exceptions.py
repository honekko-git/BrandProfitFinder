"""
Fashionphile marketplace exceptions.
"""


class FashionphileError(Exception):
    """Base exception for Fashionphile marketplace failures."""


class FashionphileConfigurationError(FashionphileError):
    """Raised when Fashionphile configuration or client is missing."""


class FashionphileClientError(FashionphileError):
    """Raised when Fashionphile client operations fail."""


class FashionphileResponseError(FashionphileError):
    """Raised when Fashionphile response payload structure is invalid."""


class FashionphileParseError(FashionphileError):
    """Raised when Fashionphile item data cannot be parsed."""
