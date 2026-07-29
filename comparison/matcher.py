"""
Deterministic product identity helpers for cross-marketplace comparison.
"""

from __future__ import annotations

from decimal import Decimal

from comparison.util import stable_unique
from product_identity.adapter import ProductIdentityService
from product_identity.enums import IdentityDecision
from product_identity.models import ProductIdentityResult
from product_identity.policy import decision_allows_comparison_result
from models.marketplace_listing import MarketplaceListing
from models.product import Product


class ComparisonIdentityMatcher:
    """Validate that marketplace listings represent the same overseas product."""

    def __init__(self, identity_service: ProductIdentityService | None = None) -> None:
        self._identity_service = identity_service or ProductIdentityService()

    def evaluate(
        self,
        product: Product,
        listing: MarketplaceListing | None,
        *,
        min_score: Decimal,
    ) -> tuple[bool, Decimal | None, list[str]]:
        """
        Determine whether a selected listing matches the product identity.

        Preserves the Phase 18 return contract for historical callers:
        ``(is_match, compatibility score, warnings)``.
        """
        if listing is None:
            return False, None, ["no selected listing"]

        score = self._identity_service.legacy_match_score(product, listing)
        warnings = self._identity_service.legacy_warnings(product, listing)
        is_match = score >= min_score
        if not is_match:
            warnings = [*warnings, f"identity match score below threshold ({score} < {min_score})"]
        return is_match, score, stable_unique(warnings)

    def evaluate_with_identity(
        self,
        product: Product,
        listing: MarketplaceListing | None,
        *,
        min_score: Decimal,
    ) -> tuple[bool, Decimal | None, list[str], ProductIdentityResult | None]:
        """
        Evaluate identity with explainable structured result.

        Returns:
            Tuple of (eligible_for_comparison, score, warnings, identity_result).

        ``eligible_for_comparison`` is True when the decision is not ``NO_MATCH``
        and the legacy compatibility score meets ``min_score``. ``INSUFFICIENT_DATA``
        and ``REVIEW`` remain visible and reviewable but are never authoritative
        ``MATCH`` decisions.
        """
        if listing is None:
            return False, None, ["no selected listing"], None

        identity_result = self._identity_service.evaluate_product_listing(product, listing)
        score = Decimal(str(identity_result.identity_score or 0)).quantize(Decimal("0.01"))
        warnings = self._identity_service.legacy_warnings(product, listing)
        warnings.extend(identity_result.warnings)
        if identity_result.review_required:
            warnings.append(f"identity review required: {identity_result.decision.value}")

        eligible = decision_allows_comparison_result(identity_result, score, min_score)
        if not eligible and identity_result.decision == IdentityDecision.REVIEW:
            warnings.append(f"identity match score below threshold ({score} < {min_score})")
        elif not eligible and identity_result.decision in {
            IdentityDecision.NO_MATCH,
            IdentityDecision.INSUFFICIENT_DATA,
        }:
            warnings.append(f"identity decision {identity_result.decision.value}")
        elif not eligible:
            warnings.append(f"identity match score below threshold ({score} < {min_score})")

        return eligible, score, stable_unique(warnings), identity_result

    def resolve_for_candidate(
        self,
        product: Product,
        candidate_listing: MarketplaceListing | None,
        *,
        identity_listing: MarketplaceListing | None,
        identity_result: ProductIdentityResult | None,
        match_score: Decimal | None,
        match_warnings: list[str],
        min_score: Decimal,
    ) -> tuple[bool, Decimal | None, list[str], ProductIdentityResult | None]:
        """
        Reuse a prior identity evaluation when the listing has not changed.

        Falls back to ``evaluate_with_identity`` when cached identity data is absent
        or the listing reference differs from the evaluated identity listing.
        """
        if (
            identity_result is not None
            and candidate_listing is not None
            and identity_listing is candidate_listing
        ):
            score = match_score
            if score is None:
                score = Decimal(str(identity_result.identity_score or 0)).quantize(Decimal("0.01"))
            warnings = list(match_warnings)
            if not warnings:
                warnings = list(identity_result.warnings)
            eligible = decision_allows_comparison_result(identity_result, score, min_score)
            return eligible, score, stable_unique(warnings), identity_result

        return self.evaluate_with_identity(
            product,
            candidate_listing,
            min_score=min_score,
        )
