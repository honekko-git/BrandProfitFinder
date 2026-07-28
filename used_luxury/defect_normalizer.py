"""
Defect normalization for used luxury items.
"""

from models.used_item_defects import DEFECT_FIELD_NAMES, DefectEntry, DefectProfile, DefectSeverity, TriState


class DefectNormalizer:
    """Normalize defect data from various sources."""

    def normalize(self, raw: dict[str, object] | None) -> DefectProfile:
        """
        Build a defect profile from raw data.

        Values may be bool, tri-state string, or severity string.

        Args:
            raw: Raw defects dictionary.

        Returns:
            Normalized DefectProfile.
        """
        profile = DefectProfile()
        if not raw:
            return profile

        for key, value in raw.items():
            name = str(key).strip().lower()
            if name not in DEFECT_FIELD_NAMES:
                continue
            entry = self._parse_entry(value)
            profile.entries[name] = entry

        return profile

    def _parse_entry(self, value: object) -> DefectEntry:
        if isinstance(value, dict):
            present = TriState.from_value(value.get("present", value.get("value")))
            severity = DefectSeverity.from_value(value.get("severity"))
            if present == TriState.UNKNOWN and severity != DefectSeverity.UNKNOWN:
                present = TriState.TRUE
            return DefectEntry(present=present, severity=severity)

        text = str(value).strip().lower() if value is not None else ""
        if text in {"minor", "moderate", "major", "critical"}:
            return DefectEntry(present=TriState.TRUE, severity=DefectSeverity.from_value(text))
        present = TriState.from_value(value)
        severity = DefectSeverity.UNKNOWN
        if present == TriState.TRUE:
            severity = DefectSeverity.UNKNOWN
        elif present == TriState.FALSE:
            severity = DefectSeverity.NONE
        return DefectEntry(present=present, severity=severity)
