"""Condition detection and compatibility for comparable matching."""

from __future__ import annotations

import re
from enum import StrEnum


class ProductCondition(StrEnum):
    """Normalized product condition."""

    NEW_WITH_TAGS = "NEW_WITH_TAGS"
    LIKE_NEW = "LIKE_NEW"
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    FAIR = "FAIR"
    POOR = "POOR"
    JUNK = "JUNK"
    UNKNOWN = "UNKNOWN"


CONDITION_PATTERNS: tuple[tuple[ProductCondition, tuple[str, ...]], ...] = (
    (ProductCondition.NEW_WITH_TAGS, ("new with tags", "nwt", "新品", "タグ付き", "未使用")),
    (ProductCondition.LIKE_NEW, ("like new", "almost new", "未使用に近い", "極美品")),
    (ProductCondition.EXCELLENT, ("excellent", "ex condition", "美品", "極上")),
    (ProductCondition.GOOD, ("very good", "good", "良品", "使用感あり")),
    (ProductCondition.FAIR, ("fair", "used", "中古", "やや傷")),
    (ProductCondition.POOR, ("poor", "heavy wear", "傷多", "状態悪")),
    (ProductCondition.JUNK, ("junk", "ジャンク", "訳あり", "repair", "修理", "parts", "部品")),
)

EXCLUDED_CONDITIONS = {ProductCondition.JUNK, ProductCondition.POOR}

REPAIR_MARKERS = ("repair", "修理", "parts only", "部品", "ジャンク", "訳あり")


def detect_condition(text: str) -> ProductCondition:
    """Detect condition from title or condition field."""
    normalized = re.sub(r"\s+", " ", text.lower()).strip()
    for condition, patterns in CONDITION_PATTERNS:
        if any(pattern in normalized for pattern in patterns):
            return condition
    return ProductCondition.UNKNOWN


def is_condition_excluded(text: str) -> bool:
    """Return True when title/condition indicates junk/repair inventory."""
    normalized = text.lower()
    if any(marker in normalized for marker in REPAIR_MARKERS):
        return True
    detected = detect_condition(text)
    return detected in EXCLUDED_CONDITIONS


def conditions_compatible(purchase_condition: ProductCondition, sample_condition: ProductCondition) -> bool:
    """Return True when purchase and sample conditions may be compared."""
    if sample_condition in EXCLUDED_CONDITIONS:
        return False
    if purchase_condition in EXCLUDED_CONDITIONS:
        return False
    if purchase_condition == ProductCondition.UNKNOWN or sample_condition == ProductCondition.UNKNOWN:
        return True
    order = list(ProductCondition)
    try:
        purchase_idx = order.index(purchase_condition)
        sample_idx = order.index(sample_condition)
    except ValueError:
        return True
    return abs(purchase_idx - sample_idx) <= 2


def condition_reliability_penalty(purchase_condition: ProductCondition, sample_condition: ProductCondition) -> int:
    """Return reliability penalty points for condition mismatch."""
    if sample_condition == ProductCondition.UNKNOWN:
        return 1
    if not conditions_compatible(purchase_condition, sample_condition):
        return 3
    order = list(ProductCondition)
    if purchase_condition == ProductCondition.UNKNOWN:
        return 1
    gap = abs(order.index(purchase_condition) - order.index(sample_condition))
    return min(2, gap)
