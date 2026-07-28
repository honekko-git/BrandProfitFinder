"""
Defect and tri-state value models for used luxury items.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TriState(str, Enum):
    """Three-valued logic for defect presence."""

    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"

    @classmethod
    def from_value(cls, value: Any) -> "TriState":
        """
        Parse arbitrary input into a tri-state value.

        Args:
            value: Boolean, string, or None.

        Returns:
            TRUE, FALSE, or UNKNOWN.
        """
        if value is None:
            return cls.UNKNOWN
        if isinstance(value, bool):
            return cls.TRUE if value else cls.FALSE
        text = str(value).strip().lower()
        if text in {"true", "yes", "1", "present", "あり", "有"}:
            return cls.TRUE
        if text in {"false", "no", "0", "none", "なし", "無", "not_included"}:
            return cls.FALSE
        if text in {"unknown", "", "不明", "未記載", "n/a", "na"}:
            return cls.UNKNOWN
        return cls.UNKNOWN


class DefectSeverity(str, Enum):
    """Severity level for a defect."""

    NONE = "NONE"
    MINOR = "MINOR"
    MODERATE = "MODERATE"
    MAJOR = "MAJOR"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_value(cls, value: Any) -> "DefectSeverity":
        """Parse severity from string or None."""
        if value is None:
            return cls.UNKNOWN
        text = str(value).strip().lower()
        mapping = {
            "none": cls.NONE,
            "minor": cls.MINOR,
            "moderate": cls.MODERATE,
            "major": cls.MAJOR,
            "critical": cls.CRITICAL,
            "unknown": cls.UNKNOWN,
            "軽微": cls.MINOR,
            "中程度": cls.MODERATE,
            "重度": cls.MAJOR,
        }
        return mapping.get(text, cls.UNKNOWN)


DEFECT_FIELD_NAMES: tuple[str, ...] = (
    "scratches",
    "stains",
    "discoloration",
    "odor",
    "peeling",
    "cracks",
    "dents",
    "deformation",
    "hardware_wear",
    "corner_wear",
    "handle_wear",
    "interior_wear",
    "missing_parts",
    "repair_history",
    "customization",
    "name_engraving",
    "battery_degradation",
    "movement_accuracy_issue",
    "water_damage",
    "unknown_damage",
)


@dataclass
class DefectEntry:
    """One defect type with presence and severity."""

    present: TriState = TriState.UNKNOWN
    severity: DefectSeverity = DefectSeverity.UNKNOWN


@dataclass
class DefectProfile:
    """Collection of defect entries for a used item."""

    entries: dict[str, DefectEntry] = field(default_factory=dict)

    def get(self, name: str) -> DefectEntry:
        """Return defect entry, defaulting to unknown."""
        return self.entries.get(name, DefectEntry())

    def has_major_damage(self) -> bool:
        """Return True when any defect is present with MAJOR or CRITICAL severity."""
        for entry in self.entries.values():
            if entry.present == TriState.TRUE and entry.severity in {
                DefectSeverity.MAJOR,
                DefectSeverity.CRITICAL,
            }:
                return True
        return False

    def to_dict(self) -> dict[str, dict[str, str]]:
        """Serialize defects for export."""
        return {
            name: {
                "present": entry.present.value,
                "severity": entry.severity.value,
            }
            for name, entry in self.entries.items()
        }
