"""
Deterministic product identity helpers for cross-marketplace comparison.
"""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal

from product_identity.adapter import ProductIdentityService
from product_identity.enums import IdentityDecision
from product_identity.models import ProductIdentityResult
from models.marketplace_listing import MarketplaceListing
from models.product import Product


def normalize_identity_text(value: str) -> str:
    """Normalize text for deterministic identity comparisons."""
    normalized = unicodedata.normalize("NFKC", value.strip().lower())
    return re.sub(r"\s+", " ", normalized)


def product_identity_key(product: Product) -> str:
    """
    Build a stable identity key for grouping comparison candidates.

    Prefers SKU, then model, then brand+name. Reserved for future grouping use.
    """
    sku = normalize_identity_text(product.sku)
    if sku:
        return f"sku:{sku}"
    model = normalize_identity_text(product.model)
    if model:
        return f"model:{model}"
    brand = normalize_identity_text(product.brand)
    name = normalize_identity_text(product.name)
    return f"name:{brand}:{name}"


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
        return is_match, score, _stable_unique(warnings)

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

        eligible = _decision_allows_comparison(identity_result, score, min_score)
        if not eligible and identity_result.decision == IdentityDecision.REVIEW:
            warnings.append(f"identity match score below threshold ({score} < {min_score})")
        elif not eligible and identity_result.decision in {
            IdentityDecision.NO_MATCH,
            IdentityDecision.INSUFFICIENT_DATA,
        }:
            warnings.append(f"identity decision {identity_result.decision.value}")
        elif not eligible:
            warnings.append(f"identity match score below threshold ({score} < {min_score})")

        return eligible, score, _stable_unique(warnings), identity_result


def _decision_allows_comparison(
    result: ProductIdentityResult,
    score: Decimal,
    min_score: Decimal,
) -> bool:
    """Return True when a listing may participate in comparison selection."""
    if result.decision == IdentityDecision.NO_MATCH:
        return False
    return score >= min_score


def _stable_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered
