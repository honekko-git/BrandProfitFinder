"""
Authentication and authenticity models for used luxury items.
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any


class AuthenticationStatus(str, Enum):
    """Authentication review status for a used item."""

    AUTHENTICATED = "AUTHENTICATED"
    SELLER_CLAIM_ONLY = "SELLER_CLAIM_ONLY"
    PLATFORM_REVIEWED = "PLATFORM_REVIEWED"
    THIRD_PARTY_REVIEWED = "THIRD_PARTY_REVIEWED"
    NOT_AUTHENTICATED = "NOT_AUTHENTICATED"
    AUTHENTICITY_CONCERN = "AUTHENTICITY_CONCERN"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_value(cls, value: Any) -> "AuthenticationStatus":
        """Parse authentication status from input."""
        if value is None:
            return cls.UNKNOWN
        text = str(value).strip().upper().replace("-", "_").replace(" ", "_")
        aliases = {
            "AUTHENTIC": cls.AUTHENTICATED,
            "VERIFIED": cls.AUTHENTICATED,
            "PLATFORM_AUTHENTICATED": cls.PLATFORM_REVIEWED,
            "THIRD_PARTY_AUTHENTICATED": cls.THIRD_PARTY_REVIEWED,
        }
        if text in aliases:
            return aliases[text]
        try:
            return cls(text)
        except ValueError:
            return cls.UNKNOWN


@dataclass
class AuthenticationInfo:
    """Authenticity and authentication details."""

    status: AuthenticationStatus = AuthenticationStatus.UNKNOWN
    provider: str = ""
    method: str = ""
    certificate_number: str = ""
    authenticity_guarantee: bool | None = None
    seller_claimed_authentic: bool | None = None
    platform_authenticated: bool | None = None
    third_party_authenticated: bool | None = None
    authentication_date: str = ""
    notes: str = ""
    warnings: list[str] = field(default_factory=list)

    def is_definitively_authenticated(self) -> bool:
        """Return True only for explicit authenticated statuses."""
        return self.status in {
            AuthenticationStatus.AUTHENTICATED,
            AuthenticationStatus.PLATFORM_REVIEWED,
            AuthenticationStatus.THIRD_PARTY_REVIEWED,
        }
