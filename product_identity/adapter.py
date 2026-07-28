"""Compatibility adapter for legacy ListingMatcher scoring."""

from __future__ import annotations

from decimal import Decimal

from marketplace.listing_matcher import ListingMatcher
from models.marketplace_listing import MarketplaceListing
from models.product import Product
from product_identity.enums import IdentityComparisonLevel, IdentityConfidence, IdentityDecision
from product_identity.evaluator import ProductIdentityEvaluator
from product_identity.extractor import extract_from_listing, extract_from_product
from product_identity.models import ProductIdentityResult


class ProductIdentityService:
    """Evaluate product/listing identity with explainable decisions."""

    def __init__(
        self,
        evaluator: ProductIdentityEvaluator | None = None,
        listing_matcher: ListingMatcher | None = None,
    ) -> None:
        self._evaluator = evaluator or ProductIdentityEvaluator()
        self._listing_matcher = listing_matcher or ListingMatcher()

    def evaluate_product_listing(
        self,
        product: Product,
        listing: MarketplaceListing | None,
        *,
        comparison_level: IdentityComparisonLevel = IdentityComparisonLevel.EXACT_VARIANT,
    ) -> ProductIdentityResult:
        if listing is None:
            return ProductIdentityResult(
                decision=IdentityDecision.INSUFFICIENT_DATA,
                confidence=IdentityConfidence.UNKNOWN,
                comparison_level=comparison_level,
                identity_score=None,
                hard_conflict=False,
                review_required=True,
                family_compatible=None,
                exact_variant_confirmed=None,
                reasons=("no selected listing",),
            )
        left = extract_from_product(product)
        right = extract_from_listing(listing)
        compatibility_score = float(self._listing_matcher.score(product, listing))
        return self._evaluator.evaluate(
            left,
            right,
            comparison_level=comparison_level,
            compatibility_score=compatibility_score,
        )

    def legacy_match_score(self, product: Product, listing: MarketplaceListing) -> Decimal:
        """Preserve Phase 18 numeric compatibility score from ListingMatcher."""
        return self._listing_matcher.score(product, listing)

    def legacy_warnings(self, product: Product, listing: MarketplaceListing) -> list[str]:
        """Preserve ListingMatcher comparison warnings."""
        return list(self._listing_matcher.get_comparison_warnings(product, listing))
