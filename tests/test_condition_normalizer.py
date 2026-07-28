"""Tests for used_luxury.condition_normalizer."""

import pytest

from models.used_item_condition import UsedItemCondition
from used_luxury.condition_normalizer import ConditionNormalizer


@pytest.fixture
def normalizer() -> ConditionNormalizer:
    return ConditionNormalizer()


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("new", UsedItemCondition.NEW),
        ("brand new", UsedItemCondition.NEW),
        ("unused", UsedItemCondition.UNUSED),
        ("never used", UsedItemCondition.UNUSED),
        ("like new", UsedItemCondition.LIKE_NEW),
        ("mint", UsedItemCondition.LIKE_NEW),
        ("excellent", UsedItemCondition.EXCELLENT),
        ("very good", UsedItemCondition.VERY_GOOD),
        ("good", UsedItemCondition.GOOD),
        ("fair", UsedItemCondition.FAIR),
        ("poor", UsedItemCondition.POOR),
        ("damaged", UsedItemCondition.POOR),
        ("for parts", UsedItemCondition.FOR_PARTS),
        ("used", UsedItemCondition.USED_GENERIC),
        ("preowned", UsedItemCondition.USED_GENERIC),
        ("pre-owned", UsedItemCondition.USED_GENERIC),
        ("中古", UsedItemCondition.USED_GENERIC),
        ("未使用", UsedItemCondition.UNUSED),
        ("新品同様", UsedItemCondition.LIKE_NEW),
        ("美品", UsedItemCondition.EXCELLENT),
        ("良好", UsedItemCondition.GOOD),
        ("  VERY GOOD  ", UsedItemCondition.VERY_GOOD),
    ],
)
def test_normalize_known_conditions(normalizer: ConditionNormalizer, raw: str, expected: UsedItemCondition) -> None:
    result = normalizer.normalize(raw)
    assert result.normalized_condition == expected
    assert result.raw_condition == raw.strip()


def test_none_returns_unknown(normalizer: ConditionNormalizer) -> None:
    result = normalizer.normalize(None)
    assert result.normalized_condition == UsedItemCondition.UNKNOWN
    assert result.confidence == 0.0


def test_empty_returns_unknown(normalizer: ConditionNormalizer) -> None:
    result = normalizer.normalize("")
    assert result.normalized_condition == UsedItemCondition.UNKNOWN


def test_unknown_word(normalizer: ConditionNormalizer) -> None:
    result = normalizer.normalize("mystery grade")
    assert result.normalized_condition == UsedItemCondition.UNKNOWN
    assert result.warnings


def test_exact_match_high_confidence(normalizer: ConditionNormalizer) -> None:
    result = normalizer.normalize("excellent")
    assert result.confidence >= 0.9


def test_ambiguous_used_not_upgraded(normalizer: ConditionNormalizer) -> None:
    result = normalizer.normalize("used")
    assert result.normalized_condition == UsedItemCondition.USED_GENERIC
    assert result.normalized_condition != UsedItemCondition.GOOD
    assert any("ambiguous" in w for w in result.warnings)


def test_raw_preserved(normalizer: ConditionNormalizer) -> None:
    result = normalizer.normalize("  Like New  ")
    assert result.raw_condition == "Like New"
