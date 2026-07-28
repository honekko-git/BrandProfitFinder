"""Tests for UsedItemDetails model."""

from models.used_item_condition import UsedItemCondition
from models.used_item_details import ConditionScoreResult, UsedItemDetails


def test_defaults() -> None:
    details = UsedItemDetails()
    assert details.condition == UsedItemCondition.UNKNOWN
    assert details.warnings == []
    assert details.risk is None


def test_optional_fields() -> None:
    details = UsedItemDetails(
        condition=UsedItemCondition.EXCELLENT,
        condition_raw="Excellent",
        condition_confidence=0.95,
        data_completeness=0.8,
    )
    assert details.condition_raw == "Excellent"
    assert details.condition_confidence == 0.95


def test_score_properties() -> None:
    details = UsedItemDetails(condition_score=ConditionScoreResult(score=85, confidence=0.9))
    assert details.condition_score_value == 85
    assert details.condition_score_confidence == 0.9


def test_risk_properties_empty() -> None:
    details = UsedItemDetails()
    assert details.risk_level is None
    assert details.risk_flags == []
