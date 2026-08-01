"""Luxury material detection for comparable product matching."""

from __future__ import annotations

from enum import StrEnum

from marketplace.browser_acquisition.listing_identity import (
    materials_compatible as identity_materials_compatible,
    normalize_material,
)


class LuxuryMaterial(StrEnum):
    """Normalized luxury leather/material label."""

    CAVIAR = "Caviar"
    LAMBSKIN = "Lambskin"
    CALFSKIN = "Calfskin"
    PATENT = "Patent"
    EPI = "Epi"
    DAMIER = "Damier"
    MONOGRAM = "Monogram"
    CANVAS = "Canvas"
    LEATHER = "Leather"
    OTHER = "Other"
    UNKNOWN = "Unknown"


_IDENTITY_TO_ENUM: dict[str, LuxuryMaterial] = {
    "CAVIAR": LuxuryMaterial.CAVIAR,
    "LAMBSKIN": LuxuryMaterial.LAMBSKIN,
    "CALFSKIN": LuxuryMaterial.CALFSKIN,
    "PATENT": LuxuryMaterial.PATENT,
    "EPI": LuxuryMaterial.EPI,
    "DAMIER": LuxuryMaterial.DAMIER,
    "MONOGRAM": LuxuryMaterial.MONOGRAM,
    "CANVAS": LuxuryMaterial.CANVAS,
    "LEATHER": LuxuryMaterial.LEATHER,
    "EPSOM": LuxuryMaterial.OTHER,
    "SAFFIANO": LuxuryMaterial.OTHER,
    "UNKNOWN": LuxuryMaterial.UNKNOWN,
}


def detect_luxury_material(title: str) -> LuxuryMaterial:
    """Detect material from listing title."""
    canonical = normalize_material(title)
    return _IDENTITY_TO_ENUM.get(canonical, LuxuryMaterial.UNKNOWN)


def materials_compatible(purchase_material: LuxuryMaterial, sample_material: LuxuryMaterial) -> bool:
    """Return True when materials can be compared."""
    return identity_materials_compatible(purchase_material.name, sample_material.name)
