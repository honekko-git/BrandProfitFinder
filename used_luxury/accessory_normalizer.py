"""
Accessory normalization for used luxury items.
"""

from models.accessory_info import (
    ACCESSORY_ALIASES,
    ACCESSORY_FIELD_NAMES,
    AccessoryCompleteness,
    AccessoryProfile,
    AccessoryStatus,
)


class AccessoryNormalizer:
    """Normalize accessory data from various sources."""

    def normalize(self, raw: dict[str, object] | None) -> AccessoryProfile:
        """
        Build an accessory profile from raw data.

        Args:
            raw: Dictionary of accessory name to status value.

        Returns:
            Normalized AccessoryProfile with completeness assessment.
        """
        profile = AccessoryProfile()
        if not raw:
            return profile

        for key, value in raw.items():
            canonical = ACCESSORY_ALIASES.get(str(key).strip().lower(), str(key).strip().lower())
            if canonical not in ACCESSORY_FIELD_NAMES and canonical not in ACCESSORY_ALIASES.values():
                canonical = str(key).strip().lower()
            profile.items[canonical] = AccessoryStatus.from_value(value)

        profile.completeness = self.assess_completeness(profile)
        return profile

    def assess_completeness(self, profile: AccessoryProfile) -> AccessoryCompleteness:
        """
        Assess accessory completeness without category-specific assumptions.

        Args:
            profile: Normalized accessory profile.

        Returns:
            Completeness level based on known included/not-included counts.
        """
        if not profile.items:
            return AccessoryCompleteness.UNKNOWN

        known = profile.known_count()
        if known == 0:
            return AccessoryCompleteness.UNKNOWN

        included = profile.included_count()
        not_included = sum(
            1 for status in profile.items.values() if status == AccessoryStatus.NOT_INCLUDED
        )

        if included == 0 and not_included > 0:
            return AccessoryCompleteness.ITEM_ONLY
        if included > 0 and not_included == 0 and known == len(profile.items):
            return AccessoryCompleteness.COMPLETE
        if included > 0 and not_included > 0:
            if included >= not_included:
                return AccessoryCompleteness.MOSTLY_COMPLETE
            return AccessoryCompleteness.PARTIAL
        if included > 0:
            return AccessoryCompleteness.PARTIAL
        return AccessoryCompleteness.UNKNOWN
