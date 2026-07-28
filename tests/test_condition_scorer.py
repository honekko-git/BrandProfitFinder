"""Tests for condition scorer."""

from models.accessory_info import AccessoryCompleteness, AccessoryProfile, AccessoryStatus
from models.used_item_condition import UsedItemCondition
from models.used_item_defects import DefectEntry, DefectProfile, DefectSeverity, TriState
from used_luxury.condition_scorer import ConditionScorer


def test_base_scores() -> None:
    scorer = ConditionScorer()
    assert scorer.score(UsedItemCondition.NEW).score == 100
    assert scorer.score(UsedItemCondition.EXCELLENT).score == 85
    assert scorer.score(UsedItemCondition.FOR_PARTS).score == 5


def test_unknown_no_score() -> None:
    result = ConditionScorer().score(UsedItemCondition.UNKNOWN)
    assert result.score is None


def test_scratch_deduction() -> None:
    defects = DefectProfile(entries={"scratches": DefectEntry(TriState.TRUE, DefectSeverity.MINOR)})
    result = ConditionScorer().score(UsedItemCondition.VERY_GOOD, defects=defects)
    assert result.score is not None
    assert result.score < 75


def test_stain_deduction() -> None:
    defects = DefectProfile(entries={"stains": DefectEntry(TriState.TRUE, DefectSeverity.MODERATE)})
    result = ConditionScorer().score(UsedItemCondition.GOOD, defects=defects)
    assert result.score is not None
    assert result.score < 65


def test_missing_accessories_deduction() -> None:
    accessories = AccessoryProfile(completeness=AccessoryCompleteness.ITEM_ONLY)
    result = ConditionScorer().score(UsedItemCondition.GOOD, accessories=accessories)
    assert result.score is not None
    assert result.score < 65


def test_major_damage_low_score() -> None:
    defects = DefectProfile(entries={"cracks": DefectEntry(TriState.TRUE, DefectSeverity.CRITICAL)})
    result = ConditionScorer().score(UsedItemCondition.FAIR, defects=defects)
    assert result.score is not None
    assert result.score <= 45


def test_score_bounds() -> None:
    defects = DefectProfile(
        entries={
            "cracks": DefectEntry(TriState.TRUE, DefectSeverity.CRITICAL),
            "stains": DefectEntry(TriState.TRUE, DefectSeverity.CRITICAL),
        }
    )
    result = ConditionScorer().score(UsedItemCondition.NEW, defects=defects)
    assert result.score is not None
    assert 0 <= result.score <= 100


def test_unknown_defect_not_treated_as_absent() -> None:
    defects = DefectProfile(entries={"odor": DefectEntry(TriState.UNKNOWN, DefectSeverity.UNKNOWN)})
    result = ConditionScorer().score(UsedItemCondition.GOOD, defects=defects)
    assert any("unknown" in w for w in result.warnings)
