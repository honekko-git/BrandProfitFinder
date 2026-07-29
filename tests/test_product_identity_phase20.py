"""Phase 20: identity policy hardening and marketplace adapter standardization."""

from __future__ import annotations

from decimal import Decimal

from comparison.matcher import ComparisonIdentityMatcher
from models.marketplace_listing import MarketplaceListing
from models.product import Product
from product_identity.adapter import ProductIdentityService
from product_identity.enums import (
    BroadCategory,
    EvidenceOutcome,
    EvidenceStrength,
    IdentityComparisonLevel,
    IdentityDecision,
    IdentifierType,
)
from product_identity.evaluator import ProductIdentityEvaluator
from product_identity.evidence import collect_evidence
from product_identity.models import IdentityEvidence, ProductIdentityProfile
from product_identity.policy import (
    brand_confirmed,
    decision_allows_comparison,
    is_authoritative_match,
    manufacturer_strong_without_brand,
    resolve_identity_decision,
)
from product_identity.identifiers import build_identifier
from product_identity.config import IdentityConfig
from marketplace.adapter import MarketplaceAdapter
from marketplace.goat_marketplace import GoatMarketplace
from marketplace.stockx_marketplace import StockXMarketplace


def _listing(**kwargs) -> MarketplaceListing:
    data = {
        "marketplace_name": "demo",
        "listing_id": "L-1",
        "title": "Demo",
        "brand": "DemoBrand",
        "model_number": "MODEL-A",
        "currency": "JPY",
        "price_jpy": Decimal("10000"),
    }
    data.update(kwargs)
    price = Decimal(str(data.pop("price_jpy")))
    meta = data.pop("source_metadata", {})
    return MarketplaceListing(**data, price_jpy=price, source_metadata=meta)


def test_missing_brand_same_model_returns_review_not_match() -> None:
    left = ProductIdentityProfile(brand="DemoBrand", model_number="M1")
    right = ProductIdentityProfile(brand=None, model_number="M1")
    result = ProductIdentityEvaluator().evaluate(left, right, compatibility_score=40.0)
    assert result.decision == IdentityDecision.REVIEW
    assert result.review_required is True
    assert result.comparison_level == IdentityComparisonLevel.EXACT_VARIANT


def test_both_missing_brand_same_model_returns_review() -> None:
    left = ProductIdentityProfile(model_number="M1")
    right = ProductIdentityProfile(model_number="M1")
    result = ProductIdentityEvaluator().evaluate(left, right, compatibility_score=40.0)
    assert result.decision == IdentityDecision.REVIEW
    assert result.review_required is True


def test_different_brands_same_model_returns_no_match() -> None:
    left = ProductIdentityProfile(brand="BrandA", model_number="M1")
    right = ProductIdentityProfile(brand="BrandB", model_number="M1")
    result = ProductIdentityEvaluator().evaluate(left, right, compatibility_score=40.0)
    assert result.decision == IdentityDecision.NO_MATCH
    assert "brand" in result.conflicting_fields


def test_valid_gtin_without_brand_still_matches() -> None:
    jan_id = build_identifier(IdentifierType.JAN, "4006381333931", source_field="jan")
    assert jan_id is not None
    left = ProductIdentityProfile(structured_identifiers=(jan_id,))
    right = ProductIdentityProfile(structured_identifiers=(jan_id,))
    result = ProductIdentityEvaluator().evaluate(left, right, compatibility_score=40.0)
    assert result.decision == IdentityDecision.MATCH


def test_invalid_gtin_does_not_force_match() -> None:
    bad = build_identifier(IdentifierType.GTIN, "123", source_field="gtin")
    assert bad is not None
    left = ProductIdentityProfile(structured_identifiers=(bad,))
    right = ProductIdentityProfile(structured_identifiers=(bad,))
    result = ProductIdentityEvaluator().evaluate(left, right, compatibility_score=40.0)
    assert result.decision != IdentityDecision.MATCH


def test_marketplace_local_sku_alone_never_authoritative_match() -> None:
    product = Product(brand="", model="", sku="LOCAL-1", name="Generic Item")
    listing = _listing(title="Generic Item", brand="", model_number="", sku="LOCAL-1")
    result = ProductIdentityService().evaluate_product_listing(product, listing)
    assert result.decision != IdentityDecision.MATCH


def test_exact_variant_conflict_blocks_match() -> None:
    left = ProductIdentityProfile(
        brand="DemoBrand",
        model_number="M1",
        category=BroadCategory.FOOTWEAR,
        size_value="10",
        size_system="US",
    )
    right = ProductIdentityProfile(
        brand="DemoBrand",
        model_number="M1",
        category=BroadCategory.FOOTWEAR,
        size_value="11",
        size_system="US",
    )
    result = ProductIdentityEvaluator().evaluate(left, right, compatibility_score=40.0)
    assert result.decision == IdentityDecision.NO_MATCH
    assert "size" in result.conflicting_fields


def test_deterministic_repeated_evaluation() -> None:
    left = ProductIdentityProfile(brand="DemoBrand", model_number="M1")
    right = ProductIdentityProfile(brand=None, model_number="M1")
    evaluator = ProductIdentityEvaluator()
    first = evaluator.evaluate(left, right, compatibility_score=40.0)
    second = evaluator.evaluate(left, right, compatibility_score=40.0)
    assert first.decision == second.decision
    assert first.review_required == second.review_required
    assert first.comparison_level == second.comparison_level
    assert first.warnings == second.warnings
    assert first.reasons == second.reasons


def test_policy_centralizes_decision_outcomes() -> None:
    config = IdentityConfig()
    left = ProductIdentityProfile(brand="DemoBrand", model_number="M1")
    right = ProductIdentityProfile(brand=None, model_number="M1")
    evidence = collect_evidence(left, right)
    outcome = resolve_identity_decision(
        evidence,
        comparison_level=IdentityComparisonLevel.EXACT_VARIANT,
        left=left,
        right=right,
        config=config,
    )
    assert outcome.decision == IdentityDecision.REVIEW

    conflict = IdentityEvidence(
        field="brand",
        evidence_type="brand",
        left_original="BrandA",
        right_original="BrandB",
        left_normalized="branda",
        right_normalized="brandb",
        outcome=EvidenceOutcome.CONFLICT,
        strength=EvidenceStrength.MEDIUM,
        explanation="brand conflict",
        hard_conflict=True,
    )
    model = IdentityEvidence(
        field="model_number",
        evidence_type="model_number",
        left_original="M1",
        right_original="M1",
        left_normalized="m1",
        right_normalized="m1",
        outcome=EvidenceOutcome.AGREE,
        strength=EvidenceStrength.STRONG,
        explanation="model agree",
    )
    no_match = resolve_identity_decision(
        (conflict, model),
        comparison_level=IdentityComparisonLevel.EXACT_VARIANT,
        left=ProductIdentityProfile(brand="BrandA", model_number="M1"),
        right=ProductIdentityProfile(brand="BrandB", model_number="M1"),
        config=config,
    )
    assert no_match.decision == IdentityDecision.NO_MATCH

    insufficient = resolve_identity_decision(
        (),
        comparison_level=IdentityComparisonLevel.EXACT_VARIANT,
        left=ProductIdentityProfile(),
        right=ProductIdentityProfile(),
        config=config,
    )
    assert insufficient.decision == IdentityDecision.INSUFFICIENT_DATA


def test_policy_brand_and_manufacturer_helpers() -> None:
    brand_evidence = (
        IdentityEvidence(
            field="brand",
            evidence_type="brand",
            left_original="Demo",
            right_original="Demo",
            left_normalized="demo",
            right_normalized="demo",
            outcome=EvidenceOutcome.AGREE,
            strength=EvidenceStrength.MEDIUM,
            explanation="brand agree",
        ),
    )
    model_evidence = (
        IdentityEvidence(
            field="model_number",
            evidence_type="model_number",
            left_original="M1",
            right_original="M1",
            left_normalized="m1",
            right_normalized="m1",
            outcome=EvidenceOutcome.AGREE,
            strength=EvidenceStrength.STRONG,
            explanation="model agree",
        ),
    )
    assert brand_confirmed(brand_evidence) is True
    assert manufacturer_strong_without_brand(list(model_evidence), brand_confirmed_flag=False) is True
    assert manufacturer_strong_without_brand(list(model_evidence), brand_confirmed_flag=True) is False


def test_decision_allows_comparison_and_authoritative_match() -> None:
    assert decision_allows_comparison(IdentityDecision.INSUFFICIENT_DATA, Decimal("40"), Decimal("30")) is True
    assert decision_allows_comparison(IdentityDecision.NO_MATCH, Decimal("40"), Decimal("30")) is False
    assert is_authoritative_match(IdentityDecision.MATCH) is True
    assert is_authoritative_match(IdentityDecision.REVIEW) is False


def test_comparison_matcher_missing_brand_same_model_eligible_with_review() -> None:
    product = Product(brand="DemoBrand", model="M1", sku="SKU-1", name="DemoBrand M1")
    listing = _listing(title="DemoBrand M1", brand="", model_number="M1")
    eligible, score, warnings, identity_result = ComparisonIdentityMatcher().evaluate_with_identity(
        product,
        listing,
        min_score=Decimal("30"),
    )
    assert eligible is True
    assert score is not None
    assert identity_result is not None
    assert identity_result.decision == IdentityDecision.REVIEW
    assert any("identity review required" in warning.lower() for warning in warnings)


def test_marketplace_adapter_interface_stockx_and_goat() -> None:
    stockx = StockXMarketplace()
    goat = GoatMarketplace()
    assert isinstance(stockx, MarketplaceAdapter)
    assert isinstance(goat, MarketplaceAdapter)
    assert stockx.adapter_id == "stockx"
    assert goat.adapter_id == "goat"
    assert stockx.uses_fixture_data is True
    assert goat.uses_fixture_data is True
    assert stockx.supports_structured_identifiers is True
    meta = stockx.adapter_metadata()
    assert meta["adapter_id"] == "stockx"
    assert meta["uses_fixture_data"] == "True"
