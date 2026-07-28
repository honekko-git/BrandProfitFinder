"""
Risk evaluation models for used luxury items.
"""

from dataclasses import dataclass, field
from enum import Enum


class RiskLevel(str, Enum):
    """Overall risk level for a used item listing."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class RiskFlag(str, Enum):
    """Individual risk indicators."""

    AUTHENTICITY_UNKNOWN = "AUTHENTICITY_UNKNOWN"
    AUTHENTICITY_CONCERN = "AUTHENTICITY_CONCERN"
    CONDITION_UNKNOWN = "CONDITION_UNKNOWN"
    MAJOR_DAMAGE = "MAJOR_DAMAGE"
    MISSING_ACCESSORIES = "MISSING_ACCESSORIES"
    NO_RETURNS = "NO_RETURNS"
    PRIVATE_SELLER = "PRIVATE_SELLER"
    LOW_SELLER_RATING = "LOW_SELLER_RATING"
    INSUFFICIENT_DESCRIPTION = "INSUFFICIENT_DESCRIPTION"
    PRICE_TOO_LOW = "PRICE_TOO_LOW"
    PRICE_TOO_HIGH = "PRICE_TOO_HIGH"
    MODEL_MISMATCH = "MODEL_MISMATCH"
    SERIAL_UNKNOWN = "SERIAL_UNKNOWN"
    REPAIR_HISTORY = "REPAIR_HISTORY"
    CUSTOMIZED_ITEM = "CUSTOMIZED_ITEM"
    FOR_PARTS = "FOR_PARTS"
    SHIPPING_UNKNOWN = "SHIPPING_UNKNOWN"
    UNKNOWN = "UNKNOWN"


@dataclass
class UsedItemRisk:
    """Risk evaluation result for a used item."""

    level: RiskLevel = RiskLevel.UNKNOWN
    flags: list[RiskFlag] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    score: float | None = None
    confidence: float | None = None
    warnings: list[str] = field(default_factory=list)

    def flag_values(self) -> list[str]:
        """Return flag names as strings."""
        return [flag.value for flag in self.flags]
