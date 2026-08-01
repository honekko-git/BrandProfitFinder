"""Tests for condition compatibility."""

from __future__ import annotations

from profit_discovery.discovery_validation.batch_profit.condition import (
    ProductCondition,
    conditions_compatible,
    detect_condition,
    is_condition_excluded,
)


def test_en_jp_condition_detection() -> None:
    assert detect_condition("Excellent condition Chanel wallet") == ProductCondition.EXCELLENT
    assert detect_condition("美品 シャネル 財布") == ProductCondition.EXCELLENT
    assert detect_condition("ジャンク 訳あり") == ProductCondition.JUNK


def test_junk_exclusion() -> None:
    assert is_condition_excluded("CHANEL wallet junk parts")
    assert is_condition_excluded("修理用 部品取り")


def test_unknown_is_allowed_with_penalty() -> None:
    assert conditions_compatible(ProductCondition.EXCELLENT, ProductCondition.UNKNOWN) is True


def test_large_condition_gap_not_compatible() -> None:
    assert conditions_compatible(ProductCondition.NEW_WITH_TAGS, ProductCondition.POOR) is False
