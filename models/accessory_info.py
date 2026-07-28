"""
Accessory information models for used luxury items.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AccessoryStatus(str, Enum):
    """Whether an accessory is included with the item."""

    INCLUDED = "included"
    NOT_INCLUDED = "not_included"
    UNKNOWN = "unknown"

    @classmethod
    def from_value(cls, value: Any) -> "AccessoryStatus":
        """
        Parse accessory status from input.

        Missing or blank values are UNKNOWN, not NOT_INCLUDED.
        """
        if value is None:
            return cls.UNKNOWN
        text = str(value).strip().lower()
        if text in {"included", "yes", "true", "1", "あり", "有", "付属"}:
            return cls.INCLUDED
        if text in {"not_included", "no", "false", "0", "なし", "無", "不含"}:
            return cls.NOT_INCLUDED
        if text in {"", "unknown", "不明", "未記載", "n/a", "na"}:
            return cls.UNKNOWN
        return cls.UNKNOWN


class AccessoryCompleteness(str, Enum):
    """Overall accessory completeness assessment."""

    COMPLETE = "COMPLETE"
    MOSTLY_COMPLETE = "MOSTLY_COMPLETE"
    PARTIAL = "PARTIAL"
    ITEM_ONLY = "ITEM_ONLY"
    UNKNOWN = "UNKNOWN"


ACCESSORY_FIELD_NAMES: tuple[str, ...] = (
    "original_box",
    "dust_bag",
    "warranty_card",
    "authenticity_card",
    "receipt",
    "manual",
    "tags",
    "spare_parts",
    "shoulder_strap",
    "lock",
    "key",
    "pouch",
    "case",
    "certificate",
    "extra_links",
    "charger",
    "accessories_other",
)

# Alias map from fixture keys to canonical names
ACCESSORY_ALIASES: dict[str, str] = {
    "box": "original_box",
    "papers": "certificate",
    "service_papers": "certificate",
    "hang_tag": "tags",
    "travel_case": "case",
    "original_receipt": "receipt",
}


@dataclass
class AccessoryProfile:
    """Accessory inclusion status for a used item."""

    items: dict[str, AccessoryStatus] = field(default_factory=dict)
    completeness: AccessoryCompleteness = AccessoryCompleteness.UNKNOWN

    def get(self, name: str) -> AccessoryStatus:
        """Return accessory status, defaulting to unknown."""
        canonical = ACCESSORY_ALIASES.get(name, name)
        return self.items.get(canonical, AccessoryStatus.UNKNOWN)

    def included_count(self) -> int:
        """Count explicitly included accessories."""
        return sum(1 for status in self.items.values() if status == AccessoryStatus.INCLUDED)

    def known_count(self) -> int:
        """Count accessories with known (non-unknown) status."""
        return sum(1 for status in self.items.values() if status != AccessoryStatus.UNKNOWN)

    def to_dict(self) -> dict[str, str]:
        """Serialize accessories for export."""
        return {name: status.value for name, status in self.items.items()}
