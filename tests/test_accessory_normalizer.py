"""Tests for accessory normalizer."""

from models.accessory_info import AccessoryCompleteness, AccessoryStatus
from used_luxury.accessory_normalizer import AccessoryNormalizer


def test_included_not_included_unknown() -> None:
    normalizer = AccessoryNormalizer()
    profile = normalizer.normalize(
        {"dust_bag": "included", "original_box": "not_included", "manual": "unknown"}
    )
    assert profile.get("dust_bag") == AccessoryStatus.INCLUDED
    assert profile.get("original_box") == AccessoryStatus.NOT_INCLUDED
    assert profile.get("manual") == AccessoryStatus.UNKNOWN


def test_missing_key_is_unknown_not_not_included() -> None:
    profile = AccessoryNormalizer().normalize({"dust_bag": "included"})
    assert profile.get("warranty_card") == AccessoryStatus.UNKNOWN


def test_box_alias() -> None:
    profile = AccessoryNormalizer().normalize({"box": "included"})
    assert profile.get("original_box") == AccessoryStatus.INCLUDED


def test_item_only_completeness() -> None:
    profile = AccessoryNormalizer().normalize(
        {"dust_bag": "not_included", "original_box": "not_included"}
    )
    assert profile.completeness == AccessoryCompleteness.ITEM_ONLY


def test_complete_completeness() -> None:
    profile = AccessoryNormalizer().normalize(
        {"dust_bag": "included", "original_box": "included"}
    )
    assert profile.completeness in {AccessoryCompleteness.COMPLETE, AccessoryCompleteness.MOSTLY_COMPLETE}


def test_invalid_value_is_unknown() -> None:
    profile = AccessoryNormalizer().normalize({"dust_bag": "maybe"})
    assert profile.get("dust_bag") == AccessoryStatus.UNKNOWN
