"""Tests for luxury material detection."""

from __future__ import annotations

from marketplace.browser_acquisition.luxury_material import LuxuryMaterial, detect_luxury_material, materials_compatible


def test_caviar_detection() -> None:
    assert detect_luxury_material("Chanel Classic Wallet Black Caviar") == LuxuryMaterial.CAVIAR
    assert detect_luxury_material("シャネル キャビアスキン 財布") == LuxuryMaterial.CAVIAR
    assert detect_luxury_material("CHANEL カビアン 黒") == LuxuryMaterial.CAVIAR


def test_lambskin_and_calfskin_detection() -> None:
    assert detect_luxury_material("Chanel lambskin wallet") == LuxuryMaterial.LAMBSKIN
    assert detect_luxury_material("ラムスキン 財布") == LuxuryMaterial.LAMBSKIN
    assert detect_luxury_material("Chanel calfskin wallet") == LuxuryMaterial.CALFSKIN
    assert detect_luxury_material("カーフレザー 財布") == LuxuryMaterial.CALFSKIN


def test_unknown_material_is_compatible() -> None:
    assert detect_luxury_material("Chanel wallet black") == LuxuryMaterial.UNKNOWN
    assert materials_compatible(LuxuryMaterial.UNKNOWN, LuxuryMaterial.CAVIAR) is True


def test_material_mismatch_not_compatible() -> None:
    assert materials_compatible(LuxuryMaterial.CAVIAR, LuxuryMaterial.LAMBSKIN) is False
    assert materials_compatible(LuxuryMaterial.CAVIAR, LuxuryMaterial.CAVIAR) is True
