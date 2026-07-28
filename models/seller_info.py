"""
Seller and return policy models for used luxury items.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any


class SellerType(str, Enum):
    """Seller category for a used item listing."""

    PRIVATE_SELLER = "PRIVATE_SELLER"
    PROFESSIONAL_SELLER = "PROFESSIONAL_SELLER"
    RETAILER = "RETAILER"
    CONSIGNMENT_STORE = "CONSIGNMENT_STORE"
    PLATFORM = "PLATFORM"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_value(cls, value: Any) -> "SellerType":
        """Parse seller type from input."""
        if value is None:
            return cls.UNKNOWN
        text = str(value).strip().upper().replace("-", "_").replace(" ", "_")
        aliases = {
            "PRIVATE": cls.PRIVATE_SELLER,
            "PROFESSIONAL": cls.PROFESSIONAL_SELLER,
            "PROFESSIONAL_DEALER": cls.PROFESSIONAL_SELLER,
            "INDIVIDUAL": cls.PRIVATE_SELLER,
        }
        if text in aliases:
            return aliases[text]
        try:
            return cls(text)
        except ValueError:
            return cls.UNKNOWN


@dataclass
class SellerDetails:
    """Seller information for a used item listing."""

    seller_type: SellerType = SellerType.UNKNOWN
    seller_rating: Decimal | None = None
    seller_review_count: int | None = None
    seller_verified: bool | None = None
    business_name: str = ""
    country: str = ""


@dataclass
class ReturnPolicy:
    """Return policy for a used item listing."""

    return_accepted: bool | None = None
    return_period_days: int | None = None
