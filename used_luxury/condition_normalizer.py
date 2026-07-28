"""
Condition normalization for used luxury items.
"""

from dataclasses import dataclass, field
import re
import unicodedata

from models.used_item_condition import UsedItemCondition


@dataclass(frozen=True)
class ConditionNormalizationResult:
    """Result of normalizing a raw condition string."""

    normalized_condition: UsedItemCondition
    raw_condition: str
    confidence: float
    matched_rule: str
    warnings: list[str] = field(default_factory=list)


# (pattern, condition, confidence, rule_name)
_CONDITION_RULES: tuple[tuple[re.Pattern[str], UsedItemCondition, float, str], ...] = (
    (re.compile(r"^(brand\s*)?new$|^新品$"), UsedItemCondition.NEW, 1.0, "exact_new"),
    (re.compile(r"^unused$|^never\s*used$|^never\s*worn$|^未使用$"), UsedItemCondition.UNUSED, 1.0, "exact_unused"),
    (re.compile(r"^like\s*new$|^新品同様$"), UsedItemCondition.LIKE_NEW, 0.95, "exact_like_new"),
    (re.compile(r"^mint$"), UsedItemCondition.LIKE_NEW, 0.9, "mint_like_new"),
    (re.compile(r"^excellent$|^美品$"), UsedItemCondition.EXCELLENT, 0.95, "exact_excellent"),
    (re.compile(r"^very\s*good$"), UsedItemCondition.VERY_GOOD, 0.95, "exact_very_good"),
    (re.compile(r"^good$|^良好$"), UsedItemCondition.GOOD, 0.9, "exact_good"),
    (re.compile(r"^fair$|^傷や汚れあり$"), UsedItemCondition.FAIR, 0.9, "exact_fair"),
    (re.compile(r"^poor$|^damaged$|^全体的に状態が悪い$"), UsedItemCondition.POOR, 0.9, "exact_poor"),
    (re.compile(r"^for\s*parts$|^ジャンク$"), UsedItemCondition.FOR_PARTS, 0.95, "exact_for_parts"),
    (re.compile(r"^pre[- ]?owned$|^second\s*hand$|^中古$"), UsedItemCondition.USED_GENERIC, 0.6, "generic_used"),
    (re.compile(r"^vintage$"), UsedItemCondition.USED_GENERIC, 0.4, "vestiaire_vintage"),
    (re.compile(r"^giftable$"), UsedItemCondition.LIKE_NEW, 0.7, "fashionphile_giftable"),
    (re.compile(r"^shows\s*wear$"), UsedItemCondition.USED_GENERIC, 0.5, "shows_wear"),
    (re.compile(r"^heavily\s*worn$"), UsedItemCondition.POOR, 0.85, "heavily_worn"),
    (re.compile(r"^as\s*is$"), UsedItemCondition.FAIR, 0.7, "as_is"),
    (re.compile(r"^used$"), UsedItemCondition.USED_GENERIC, 0.5, "ambiguous_used"),
)


class ConditionNormalizer:
    """Normalize site-specific condition strings to common values."""

    def normalize(self, raw: str | None) -> ConditionNormalizationResult:
        """
        Normalize a raw condition string.

        Args:
            raw: Raw condition text from a data source.

        Returns:
            Normalization result with confidence and warnings.
        """
        if raw is None or not str(raw).strip():
            return ConditionNormalizationResult(
                normalized_condition=UsedItemCondition.UNKNOWN,
                raw_condition=str(raw or ""),
                confidence=0.0,
                matched_rule="empty",
                warnings=["empty condition input"],
            )

        raw_text = str(raw).strip()
        normalized_key = _normalize_key(raw_text)

        # Direct enum match
        direct = UsedItemCondition.from_value(raw_text)
        if direct != UsedItemCondition.UNKNOWN:
            return ConditionNormalizationResult(
                normalized_condition=direct,
                raw_condition=raw_text,
                confidence=1.0,
                matched_rule="enum_direct",
            )

        for pattern, condition, confidence, rule in _CONDITION_RULES:
            if pattern.search(normalized_key):
                warnings: list[str] = []
                if condition == UsedItemCondition.USED_GENERIC:
                    warnings.append("ambiguous used condition; not upgraded to ranked grade")
                if rule == "vestiaire_vintage":
                    warnings.append("vintage indicates age; not upgraded to good condition")
                if rule == "fashionphile_giftable":
                    warnings.append("giftable may reflect packaging; not conflated with accessories")
                if rule == "shows_wear":
                    warnings.append("shows wear does not imply good condition grade")
                if rule == "as_is":
                    warnings.append("as is condition requires buyer caution")
                return ConditionNormalizationResult(
                    normalized_condition=condition,
                    raw_condition=raw_text,
                    confidence=confidence,
                    matched_rule=rule,
                    warnings=warnings,
                )

        return ConditionNormalizationResult(
            normalized_condition=UsedItemCondition.UNKNOWN,
            raw_condition=raw_text,
            confidence=0.0,
            matched_rule="unknown",
            warnings=[f"unrecognized condition: {raw_text}"],
        )


def _normalize_key(value: str) -> str:
    text = unicodedata.normalize("NFKC", value.strip().lower())
    return re.sub(r"\s+", " ", text)
