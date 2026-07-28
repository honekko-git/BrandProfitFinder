"""Tests for defect models and normalizer."""

from models.used_item_defects import DefectProfile, DefectSeverity, TriState
from used_luxury.defect_normalizer import DefectNormalizer


def test_tri_state_true_false_unknown() -> None:
    assert TriState.from_value(True) == TriState.TRUE
    assert TriState.from_value(False) == TriState.FALSE
    assert TriState.from_value(None) == TriState.UNKNOWN
    assert TriState.from_value("unknown") == TriState.UNKNOWN


def test_severity_parsing() -> None:
    assert DefectSeverity.from_value("minor") == DefectSeverity.MINOR
    assert DefectSeverity.from_value("invalid") == DefectSeverity.UNKNOWN


def test_normalize_multiple_defects() -> None:
    profile = DefectNormalizer().normalize(
        {"scratches": "minor", "stains": "moderate", "odor": "unknown"}
    )
    assert profile.get("scratches").present == TriState.TRUE
    assert profile.get("scratches").severity == DefectSeverity.MINOR
    assert profile.get("odor").present == TriState.UNKNOWN


def test_major_damage_detection() -> None:
    profile = DefectNormalizer().normalize({"cracks": "major", "corner_wear": "critical"})
    assert profile.has_major_damage() is True


def test_false_not_same_as_unknown() -> None:
    profile = DefectNormalizer().normalize({"scratches": False})
    entry = profile.get("scratches")
    assert entry.present == TriState.FALSE
    assert entry.severity == DefectSeverity.NONE
