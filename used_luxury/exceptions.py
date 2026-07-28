"""
Used luxury module exceptions.
"""


class UsedLuxuryError(Exception):
    """Base exception for used luxury processing."""


class UsedLuxuryValidationError(UsedLuxuryError):
    """Raised when used item details fail validation."""


class UsedLuxuryParseError(UsedLuxuryError):
    """Raised when used luxury payload cannot be parsed."""
