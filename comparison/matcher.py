"""
Deterministic product identity helpers for cross-marketplace comparison.
"""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal

from marketplace.listing_matcher import ListingMatcher
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

    def __init__(self, matcher: ListingMatcher | None = None) -> None:
        self._matcher = matcher or ListingMatcher()

    def evaluate(
        self,
        product: Product,
        listing: MarketplaceListing | None,
        *,
        min_score: Decimal,
    ) -> tuple[bool, Decimal | None, list[str]]:
        """
        Determine whether a selected listing matches the product identity.

        Returns:
            Tuple of (is_match, score, warnings).
        """
        if listing is None:
            return False, None, ["no selected listing"]

        score = self._matcher.score(product, listing)
        warnings = self._matcher.get_comparison_warnings(product, listing)
        is_match = score >= min_score
        if not is_match:
            warnings = [*warnings, f"identity match score below threshold ({score} < {min_score})"]
        return is_match, score, warnings
