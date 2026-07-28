"""Deterministic product identity evaluator."""

from __future__ import annotations

from product_identity.config import IdentityConfig
from product_identity.enums import (
    EvidenceOutcome,
    EvidenceStrength,
    IdentityComparisonLevel,
    IdentityConfidence,
    IdentityDecision,
)
from product_identity.evidence import collect_evidence
from product_identity.models import IdentityEvidence, ProductIdentityProfile, ProductIdentityResult


class ProductIdentityEvaluator:
    """Evaluate whether two profiles represent compatible product identity."""

    def __init__(self, config: IdentityConfig | None = None) -> None:
        self.config = config or IdentityConfig()

    def evaluate(
        self,
        left: ProductIdentityProfile,
        right: ProductIdentityProfile,
        *,
        comparison_level: IdentityComparisonLevel = IdentityComparisonLevel.EXACT_VARIANT,
        compatibility_score: float | None = None,
    ) -> ProductIdentityResult:
        evidence = collect_evidence(left, right)
        warnings = tuple(_stable_unique([*left.warnings, *right.warnings]))
        hard_conflicts = tuple(
            item.field
            for item in evidence
            if _hard_conflict_applies(item, comparison_level, left, self.config)
        )
        matched = tuple(
            item.field
            for item in evidence
            if item.outcome == EvidenceOutcome.AGREE and item.strength in {EvidenceStrength.STRONG, EvidenceStrength.MEDIUM}
        )
        missing = tuple(
            item.field
            for item in evidence
            if item.outcome in {EvidenceOutcome.MISSING_LEFT, EvidenceOutcome.MISSING_RIGHT, EvidenceOutcome.MISSING_BOTH}
        )

        strong_agreements = [item for item in evidence if item.outcome == EvidenceOutcome.AGREE and item.strength == EvidenceStrength.STRONG]
        medium_agreements = [item for item in evidence if item.outcome == EvidenceOutcome.AGREE and item.strength == EvidenceStrength.MEDIUM]
        weak_only = all(item.strength in {EvidenceStrength.WEAK, EvidenceStrength.INFORMATIONAL} for item in evidence if item.outcome == EvidenceOutcome.AGREE) if evidence else True

        family_compatible: bool | None = None
        exact_variant_confirmed: bool | None = None

        if hard_conflicts:
            decision = IdentityDecision.NO_MATCH
            confidence = IdentityConfidence.HIGH
            family_compatible = False
            exact_variant_confirmed = False
            reasons = ("hard structured identity conflict detected",)
        elif strong_agreements:
            decision = IdentityDecision.MATCH
            confidence = IdentityConfidence.HIGH
            family_compatible = True
            exact_variant_confirmed = _variant_confirmed(
                left, right, comparison_level, evidence, self.config
            )
            if comparison_level == IdentityComparisonLevel.EXACT_VARIANT and exact_variant_confirmed is False:
                decision = IdentityDecision.REVIEW
                reasons = ("product family appears compatible; exact variant not confirmed",)
            else:
                reasons = ("strong structured identity evidence supports compatibility",)
        elif medium_agreements and not weak_only:
            decision = IdentityDecision.REVIEW
            confidence = IdentityConfidence.MEDIUM
            family_compatible = True
            exact_variant_confirmed = _variant_confirmed(
                left, right, comparison_level, evidence, self.config
            )
            reasons = ("partial structured evidence; human review required",)
        elif any(item.field == "title_similarity" for item in evidence):
            decision = IdentityDecision.REVIEW
            confidence = IdentityConfidence.LOW
            family_compatible = None
            exact_variant_confirmed = None
            reasons = ("title similarity only; structured identifiers insufficient",)
        else:
            decision = IdentityDecision.INSUFFICIENT_DATA
            confidence = IdentityConfidence.UNKNOWN
            family_compatible = None
            exact_variant_confirmed = None
            reasons = ("insufficient structured identity evidence",)

        review_required = decision in {IdentityDecision.REVIEW, IdentityDecision.INSUFFICIENT_DATA}
        return ProductIdentityResult(
            decision=decision,
            confidence=confidence,
            comparison_level=comparison_level,
            identity_score=compatibility_score,
            hard_conflict=bool(hard_conflicts),
            review_required=review_required,
            family_compatible=family_compatible,
            exact_variant_confirmed=exact_variant_confirmed,
            matched_fields=matched,
            conflicting_fields=hard_conflicts,
            missing_fields=missing,
            evidence=evidence,
            reasons=reasons,
            warnings=warnings,
        )


def _hard_conflict_applies(
    item: IdentityEvidence,
    comparison_level: IdentityComparisonLevel,
    left: ProductIdentityProfile,
    config: IdentityConfig,
) -> bool:
    """Return True when a conflict item should produce NO_MATCH."""
    if not item.hard_conflict or item.outcome != EvidenceOutcome.CONFLICT:
        return False
    if item.field in {"size", "color", "variant"}:
        if comparison_level != IdentityComparisonLevel.EXACT_VARIANT:
            return False
        policy = config.policy_for(left.category)
        if item.field == "size" and not policy.size_defines_variant:
            return False
        if item.field == "color" and not policy.color_defines_variant:
            return False
    return True


def _variant_confirmed(
    left: ProductIdentityProfile,
    right: ProductIdentityProfile,
    comparison_level: IdentityComparisonLevel,
    evidence: tuple[IdentityEvidence, ...],
    config: IdentityConfig,
) -> bool | None:
    if comparison_level == IdentityComparisonLevel.PRODUCT_FAMILY:
        return None
    policy = config.policy_for(left.category)
    variant_conflicts = [
        item
        for item in evidence
        if item.field in {"size", "color", "variant"} and item.outcome == EvidenceOutcome.CONFLICT
    ]
    if variant_conflicts:
        return False
    if policy.size_defines_variant and (left.size_value or right.size_value):
        size_present = any(item.field == "size" and item.outcome == EvidenceOutcome.AGREE for item in evidence)
        if not size_present and left.size_value and right.size_value:
            return False
    return True


def _stable_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered
