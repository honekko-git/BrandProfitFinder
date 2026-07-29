"""Centralized identity decision policy."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from product_identity.config import IdentityConfig
from product_identity.enums import (
    EvidenceOutcome,
    EvidenceStrength,
    IdentityComparisonLevel,
    IdentityConfidence,
    IdentityDecision,
)
from product_identity.models import IdentityEvidence, ProductIdentityProfile, ProductIdentityResult

MANUFACTURER_STRONG_FIELDS: frozenset[str] = frozenset(
    {"model_number", "style_code", "reference_number"}
)
GLOBAL_STRONG_FIELDS: frozenset[str] = frozenset({"gtin", "jan", "ean", "upc"})


@dataclass(frozen=True, slots=True)
class IdentityDecisionOutcome:
    """Resolved identity decision and supporting metadata."""

    decision: IdentityDecision
    confidence: IdentityConfidence
    reasons: tuple[str, ...]
    review_required: bool
    family_compatible: bool | None
    exact_variant_confirmed: bool | None


def decision_allows_comparison(
    decision: IdentityDecision,
    score: Decimal,
    min_score: Decimal,
) -> bool:
    """Return True when a listing may participate in comparison selection."""
    if decision == IdentityDecision.NO_MATCH:
        return False
    return score >= min_score


def decision_allows_comparison_result(
    result: ProductIdentityResult,
    score: Decimal,
    min_score: Decimal,
) -> bool:
    """Return True when an identity result may participate in comparison selection."""
    return decision_allows_comparison(result.decision, score, min_score)


def is_authoritative_match(decision: IdentityDecision) -> bool:
    """Return True only for confirmed MATCH decisions."""
    return decision == IdentityDecision.MATCH


def resolve_identity_decision(
    evidence: tuple[IdentityEvidence, ...],
    *,
    comparison_level: IdentityComparisonLevel,
    left: ProductIdentityProfile,
    right: ProductIdentityProfile,
    config: IdentityConfig,
) -> IdentityDecisionOutcome:
    """Evaluate MATCH / REVIEW / INSUFFICIENT_DATA / NO_MATCH from collected evidence."""
    hard_conflicts = tuple(
        field
        for item in evidence
        for field in (item.field,)
        if hard_conflict_applies(item, comparison_level, left, config)
    )
    strong_agreements = [
        item for item in evidence if item.outcome == EvidenceOutcome.AGREE and item.strength == EvidenceStrength.STRONG
    ]
    medium_agreements = [
        item for item in evidence if item.outcome == EvidenceOutcome.AGREE and item.strength == EvidenceStrength.MEDIUM
    ]
    weak_only = (
        all(
            item.strength in {EvidenceStrength.WEAK, EvidenceStrength.INFORMATIONAL}
            for item in evidence
            if item.outcome == EvidenceOutcome.AGREE
        )
        if evidence
        else True
    )

    if hard_conflicts:
        return IdentityDecisionOutcome(
            decision=IdentityDecision.NO_MATCH,
            confidence=IdentityConfidence.HIGH,
            reasons=("hard structured identity conflict detected",),
            review_required=False,
            family_compatible=False,
            exact_variant_confirmed=False,
        )

    if strong_agreements:
        brand_ok = brand_confirmed(evidence)
        if manufacturer_strong_without_brand(strong_agreements, brand_ok):
            exact_variant_confirmed = variant_confirmed(left, right, comparison_level, evidence, config)
            return IdentityDecisionOutcome(
                decision=IdentityDecision.REVIEW,
                confidence=IdentityConfidence.MEDIUM,
                reasons=(
                    "manufacturer identifier agreement without confirmed brand context; human review required",
                ),
                review_required=True,
                family_compatible=True,
                exact_variant_confirmed=exact_variant_confirmed,
            )

        exact_variant_confirmed = variant_confirmed(left, right, comparison_level, evidence, config)
        if comparison_level == IdentityComparisonLevel.EXACT_VARIANT and exact_variant_confirmed is False:
            return IdentityDecisionOutcome(
                decision=IdentityDecision.REVIEW,
                confidence=IdentityConfidence.HIGH,
                reasons=("product family appears compatible; exact variant not confirmed",),
                review_required=True,
                family_compatible=True,
                exact_variant_confirmed=False,
            )
        return IdentityDecisionOutcome(
            decision=IdentityDecision.MATCH,
            confidence=IdentityConfidence.HIGH,
            reasons=("strong structured identity evidence supports compatibility",),
            review_required=False,
            family_compatible=True,
            exact_variant_confirmed=exact_variant_confirmed,
        )

    if medium_agreements and not weak_only:
        return IdentityDecisionOutcome(
            decision=IdentityDecision.REVIEW,
            confidence=IdentityConfidence.MEDIUM,
            reasons=("partial structured evidence; human review required",),
            review_required=True,
            family_compatible=True,
            exact_variant_confirmed=variant_confirmed(left, right, comparison_level, evidence, config),
        )

    if any(item.field == "title_similarity" for item in evidence):
        return IdentityDecisionOutcome(
            decision=IdentityDecision.REVIEW,
            confidence=IdentityConfidence.LOW,
            reasons=("title similarity only; structured identifiers insufficient",),
            review_required=True,
            family_compatible=None,
            exact_variant_confirmed=None,
        )

    return IdentityDecisionOutcome(
        decision=IdentityDecision.INSUFFICIENT_DATA,
        confidence=IdentityConfidence.UNKNOWN,
        reasons=("insufficient structured identity evidence",),
        review_required=True,
        family_compatible=None,
        exact_variant_confirmed=None,
    )


def brand_confirmed(evidence: tuple[IdentityEvidence, ...]) -> bool:
    """Return True when both sides present a matching normalized brand."""
    brand_items = [item for item in evidence if item.field == "brand"]
    if not brand_items:
        return False
    item = brand_items[0]
    return item.outcome == EvidenceOutcome.AGREE


def manufacturer_strong_without_brand(
    strong_agreements: list[IdentityEvidence],
    brand_confirmed_flag: bool,
) -> bool:
    """
    Return True when strong agreement relies on manufacturer-scoped identifiers
    without confirmed brand context.
    """
    if brand_confirmed_flag:
        return False
    has_manufacturer = any(item.field in MANUFACTURER_STRONG_FIELDS for item in strong_agreements)
    has_global_only = all(item.field in GLOBAL_STRONG_FIELDS for item in strong_agreements)
    return has_manufacturer and not has_global_only


def hard_conflict_applies(
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


def variant_confirmed(
    left: ProductIdentityProfile,
    right: ProductIdentityProfile,
    comparison_level: IdentityComparisonLevel,
    evidence: tuple[IdentityEvidence, ...],
    config: IdentityConfig,
) -> bool | None:
    """Return exact-variant confirmation state for structured variant evidence."""
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
