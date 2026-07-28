"""
Condition scoring for used luxury items.
"""

from models.accessory_info import AccessoryCompleteness, AccessoryProfile
from models.used_item_condition import CONDITION_BASE_SCORES, UsedItemCondition
from models.used_item_defects import DefectProfile, DefectSeverity, TriState
from models.used_item_details import ConditionScoreResult


SEVERITY_DEDUCTIONS: dict[DefectSeverity, int] = {
    DefectSeverity.MINOR: 3,
    DefectSeverity.MODERATE: 8,
    DefectSeverity.MAJOR: 15,
    DefectSeverity.CRITICAL: 25,
}


class ConditionScorer:
    """Score used item condition for comparison (not a substitute for facts)."""

    def score(
        self,
        condition: UsedItemCondition,
        *,
        condition_confidence: float | None = None,
        defects: DefectProfile | None = None,
        accessories: AccessoryProfile | None = None,
        data_completeness: float | None = None,
    ) -> ConditionScoreResult:
        """
        Calculate a condition score with deductions.

        Args:
            condition: Normalized condition.
            condition_confidence: Confidence in condition normalization.
            defects: Defect profile.
            accessories: Accessory profile.
            data_completeness: Data completeness ratio.

        Returns:
            ConditionScoreResult. Score is None when condition is UNKNOWN.
        """
        defects = defects or DefectProfile()
        accessories = accessories or AccessoryProfile()
        warnings: list[str] = []
        deductions: list[str] = []

        base = CONDITION_BASE_SCORES.get(condition)
        if base is None or condition == UsedItemCondition.UNKNOWN:
            return ConditionScoreResult(
                score=None,
                confidence=0.0,
                deductions=[],
                warnings=["condition unknown; no score assigned"],
                data_completeness=data_completeness,
            )

        score = float(base)

        for name, entry in defects.entries.items():
            if entry.present == TriState.TRUE:
                deduction = SEVERITY_DEDUCTIONS.get(entry.severity, 5 if entry.severity != DefectSeverity.UNKNOWN else 0)
                if entry.severity == DefectSeverity.UNKNOWN:
                    deduction = 2
                    warnings.append(f"{name}: present but severity unknown (minor deduction)")
                if deduction > 0:
                    score -= deduction
                    deductions.append(f"{name}:{entry.severity.value}:-{deduction}")
            elif entry.present == TriState.UNKNOWN:
                warnings.append(f"{name}: unknown (not treated as absent)")

        if accessories.completeness == AccessoryCompleteness.ITEM_ONLY:
            score -= 8
            deductions.append("accessories:item_only:-8")
        elif accessories.completeness == AccessoryCompleteness.PARTIAL:
            score -= 4
            deductions.append("accessories:partial:-4")

        if condition == UsedItemCondition.FOR_PARTS:
            score = min(score, 5.0)

        score = max(0.0, min(100.0, score))

        confidence = condition_confidence if condition_confidence is not None else 0.5
        if data_completeness is not None and data_completeness < 0.4:
            confidence = min(confidence, data_completeness)
            warnings.append("low data completeness reduces score confidence")

        return ConditionScoreResult(
            score=int(round(score)),
            confidence=round(confidence, 4),
            deductions=deductions,
            warnings=warnings,
            data_completeness=data_completeness,
        )
