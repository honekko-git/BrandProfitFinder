"""Deterministic product identity evaluator."""

from __future__ import annotations

from product_identity.config import IdentityConfig
from product_identity.enums import (
    EvidenceOutcome,
    EvidenceStrength,
    IdentityComparisonLevel,
    IdentityDecision,
)
from product_identity.evidence import collect_evidence
from product_identity.models import ProductIdentityProfile, ProductIdentityResult
from product_identity.policy import (
    hard_conflict_applies,
    resolve_identity_decision,
)
from product_identity.util import stable_unique


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
        warnings = tuple(stable_unique([*left.warnings, *right.warnings]))
        outcome = resolve_identity_decision(
            evidence,
            comparison_level=comparison_level,
            left=left,
            right=right,
            config=self.config,
        )
        hard_conflicts = tuple(
            item.field
            for item in evidence
            if hard_conflict_applies(item, comparison_level, left, self.config)
        )
        matched = tuple(
            item.field
            for item in evidence
            if item.outcome == EvidenceOutcome.AGREE
            and item.strength in {EvidenceStrength.STRONG, EvidenceStrength.MEDIUM}
        )
        missing = tuple(
            item.field
            for item in evidence
            if item.outcome
            in {
                EvidenceOutcome.MISSING_LEFT,
                EvidenceOutcome.MISSING_RIGHT,
                EvidenceOutcome.MISSING_BOTH,
            }
        )

        return ProductIdentityResult(
            decision=outcome.decision,
            confidence=outcome.confidence,
            comparison_level=comparison_level,
            identity_score=compatibility_score,
            hard_conflict=outcome.decision == IdentityDecision.NO_MATCH and bool(hard_conflicts),
            review_required=outcome.review_required,
            family_compatible=outcome.family_compatible,
            exact_variant_confirmed=outcome.exact_variant_confirmed,
            matched_fields=matched,
            conflicting_fields=hard_conflicts,
            missing_fields=missing,
            evidence=evidence,
            reasons=outcome.reasons,
            warnings=warnings,
        )
