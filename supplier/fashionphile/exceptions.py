"""Fashionphile supplier integration exceptions."""


class FashionphileError(Exception):
    """Base Fashionphile supplier error."""


class FashionphileConfigError(FashionphileError):
    """Raised when Fashionphile supplier configuration is invalid."""


class FashionphileLiveUnavailableError(FashionphileError):
    """Raised when Fashionphile live search is unavailable."""
