"""
Common condition values for used luxury items.
"""

from enum import Enum


class UsedItemCondition(str, Enum):
    """Normalized condition rank for used brand items."""

    NEW = "NEW"
    UNUSED = "UNUSED"
    LIKE_NEW = "LIKE_NEW"
    EXCELLENT = "EXCELLENT"
    VERY_GOOD = "VERY_GOOD"
    GOOD = "GOOD"
    FAIR = "FAIR"
    POOR = "POOR"
    FOR_PARTS = "FOR_PARTS"
    USED_GENERIC = "USED_GENERIC"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_value(cls, value: str | None) -> "UsedItemCondition":
        """
        Parse a string into a condition enum safely.

        Args:
            value: Raw or normalized condition text.

        Returns:
            Matching enum member, or UNKNOWN when unrecognized.
        """
        if not value or not str(value).strip():
            return cls.UNKNOWN
        normalized = str(value).strip().upper().replace("-", "_").replace(" ", "_")
        aliases = {
            "BRAND_NEW": cls.NEW,
            "PREOWNED": cls.USED_GENERIC,
            "PRE_OWNED": cls.USED_GENERIC,
            "SECOND_HAND": cls.USED_GENERIC,
        }
        if normalized in aliases:
            return aliases[normalized]
        try:
            return cls(normalized)
        except ValueError:
            return cls.UNKNOWN


# Base scores for condition comparison (0-100). UNKNOWN has no base score.
CONDITION_BASE_SCORES: dict[UsedItemCondition, int] = {
    UsedItemCondition.NEW: 100,
    UsedItemCondition.UNUSED: 95,
    UsedItemCondition.LIKE_NEW: 90,
    UsedItemCondition.EXCELLENT: 85,
    UsedItemCondition.VERY_GOOD: 75,
    UsedItemCondition.GOOD: 65,
    UsedItemCondition.FAIR: 45,
    UsedItemCondition.POOR: 25,
    UsedItemCondition.FOR_PARTS: 5,
    UsedItemCondition.USED_GENERIC: 55,
}

# Suggested adjustment rates (negative = discount). UNKNOWN applies no change.
CONDITION_ADJUSTMENT_RATES: dict[UsedItemCondition, float] = {
    UsedItemCondition.NEW: 0.0,
    UsedItemCondition.UNUSED: -0.02,
    UsedItemCondition.LIKE_NEW: -0.05,
    UsedItemCondition.EXCELLENT: -0.10,
    UsedItemCondition.VERY_GOOD: -0.15,
    UsedItemCondition.GOOD: -0.25,
    UsedItemCondition.FAIR: -0.40,
    UsedItemCondition.POOR: -0.60,
    UsedItemCondition.FOR_PARTS: -0.80,
    UsedItemCondition.USED_GENERIC: -0.20,
}
