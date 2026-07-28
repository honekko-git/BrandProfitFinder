"""Pre-commit review regression tests for Phase 19 product identity."""

from decimal import Decimal
from unittest.mock import patch

import pytest

from comparison.engine import ComparisonEngine
from comparison.formatter import comparison_result_to_dict
from comparison.matcher import ComparisonIdentityMatcher
from comparison.models import MarketplaceCandidate
from comparison.service import _select_identity_listing
from excel.template import MARKETPLACE_COMPARISON_COLUMNS
from models.marketplace_listing import MarketplaceListing
from models.marketplace_search_result import MarketplaceSearchResult
from models.price_result import CALCULATION_SUCCESS, PriceResult
from models.product import Product
from profit_intelligence.models import ProfitIntelligenceResult
from product_identity.adapter import ProductIdentityService
from product_identity.enums import (
    BroadCategory,
    IdentityComparisonLevel,
    IdentityConfidence,
    IdentityDecision,
    IdentifierType,
)
from product_identity.evaluator import ProductIdentityEvaluator
from product_identity.evidence import collect_evidence
from product_identity.identifiers import build_identifier
from product_identity.models import ProductIdentityProfile, ProductIdentityResult


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


def test_evaluate_preserves_phase18_three_tuple_contract() -> None:
    product = Product(brand="DemoBrand", model="MODEL-A", sku="SKU-A", name="DemoBrand Model A")
    listing = _listing(title="DemoBrand Model A", model_number="MODEL-A")
    is_match, score, warnings = ComparisonIdentityMatcher().evaluate(
        product, listing, min_score=Decimal("30")
    )
    assert isinstance(is_match, bool)
    assert isinstance(score, Decimal)
    assert isinstance(warnings, list)
    assert is_match is True


def test_evaluate_with_identity_returns_structured_result() -> None:
    product = Product(brand="DemoBrand", model="MODEL-A", sku="4006381333931", name="DemoBrand Model A")
    listing = _listing(title="DemoBrand Model A", model_number="MODEL-A", jan_code="4006381333931")
    eligible, _score, _warnings, identity_result = ComparisonIdentityMatcher().evaluate_with_identity(
        product, listing, min_score=Decimal("30")
    )
    assert eligible is True
    assert identity_result is not None
    assert identity_result.decision == IdentityDecision.MATCH


def test_no_match_never_eligible() -> None:
    product = Product(brand="DemoBrand", model="MODEL-B", sku="4006381333931", name="DemoBrand Model B")
    listing = _listing(title="DemoBrand Model B", model_number="MODEL-B", jan_code="9780201379624")
    eligible, _score, _warnings, identity_result = ComparisonIdentityMatcher().evaluate_with_identity(
        product, listing, min_score=Decimal("0")
    )
    assert identity_result is not None
    assert identity_result.decision == IdentityDecision.NO_MATCH
    assert eligible is False


def test_insufficient_data_eligible_when_legacy_score_passes() -> None:
    product = Product(brand="DemoBrand", model="MODEL-A", sku="SKU-A", name="DemoBrand Model A")
    listing = _listing(title="DemoBrand Model A", model_number="MODEL-A")
    synthetic = ProductIdentityResult(
        decision=IdentityDecision.INSUFFICIENT_DATA,
        confidence=IdentityConfidence.UNKNOWN,
        comparison_level=IdentityComparisonLevel.EXACT_VARIANT,
        identity_score=55.0,
        hard_conflict=False,
        review_required=True,
        family_compatible=None,
        exact_variant_confirmed=None,
        reasons=("insufficient structured identity evidence",),
    )
    service = ProductIdentityService()
    with patch.object(service, "evaluate_product_listing", return_value=synthetic):
        eligible, score, _warnings, identity_result = ComparisonIdentityMatcher(
            identity_service=service
        ).evaluate_with_identity(product, listing, min_score=Decimal("30"))
    assert identity_result is not None
    assert identity_result.decision == IdentityDecision.INSUFFICIENT_DATA
    assert eligible is True
    assert score >= Decimal("30")


@pytest.mark.parametrize(
    "decision,expected_eligible",
    [
        (IdentityDecision.MATCH, True),
        (IdentityDecision.REVIEW, True),
        (IdentityDecision.INSUFFICIENT_DATA, True),
        (IdentityDecision.NO_MATCH, False),
    ],
)
def test_decision_eligibility_matrix(decision: IdentityDecision, expected_eligible: bool) -> None:
    product = Product(brand="DemoBrand", model="MODEL-A", sku="SKU-A", name="DemoBrand Model A")
    listing = _listing(title="DemoBrand Model A", model_number="MODEL-A")
    synthetic = ProductIdentityResult(
        decision=decision,
        confidence=IdentityConfidence.MEDIUM,
        comparison_level=IdentityComparisonLevel.EXACT_VARIANT,
        identity_score=80.0,
        hard_conflict=decision == IdentityDecision.NO_MATCH,
        review_required=decision in {IdentityDecision.REVIEW, IdentityDecision.INSUFFICIENT_DATA},
        family_compatible=decision != IdentityDecision.NO_MATCH,
        exact_variant_confirmed=decision == IdentityDecision.MATCH,
    )
    service = ProductIdentityService()
    with patch.object(service, "evaluate_product_listing", return_value=synthetic):
        eligible, _score, _warnings, identity_result = ComparisonIdentityMatcher(
            identity_service=service
        ).evaluate_with_identity(product, listing, min_score=Decimal("30"))
    assert identity_result is not None
    assert eligible is expected_eligible


def test_same_malformed_gtin_does_not_create_agreement() -> None:
    left_id = build_identifier(IdentifierType.JAN, "123", source_field="jan")
    right_id = build_identifier(IdentifierType.JAN, "123", source_field="jan")
    assert left_id is not None and right_id is not None
    left = ProductIdentityProfile(structured_identifiers=(left_id,))
    right = ProductIdentityProfile(structured_identifiers=(right_id,))
    result = ProductIdentityEvaluator().evaluate(left, right, compatibility_score=10.0)
    assert result.decision != IdentityDecision.MATCH


def test_valid_conflicting_gtin_produces_no_match() -> None:
    left = ProductIdentityProfile(
        structured_identifiers=(
            build_identifier(IdentifierType.JAN, "4006381333931", source_field="jan"),
        )
    )
    right = ProductIdentityProfile(
        structured_identifiers=(
            build_identifier(IdentifierType.JAN, "9780201379624", source_field="jan"),
        )
    )
    result = ProductIdentityEvaluator().evaluate(left, right, compatibility_score=10.0)
    assert result.decision == IdentityDecision.NO_MATCH
    assert "jan" in result.conflicting_fields


def test_local_sku_difference_not_hard_conflict() -> None:
    product = Product(brand="DemoBrand", model="MODEL-I", sku="LOCAL-1", name="DemoBrand Model I")
    listing = _listing(title="DemoBrand Model I", model_number="MODEL-I", sku="LOCAL-2")
    result = ProductIdentityService().evaluate_product_listing(product, listing)
    assert result.decision == IdentityDecision.MATCH
    assert "sku" not in result.conflicting_fields


def test_title_overlap_with_conflicting_model_numbers() -> None:
    product = Product(
        brand="DemoBrand",
        model="MODEL-100",
        sku="SKU-T",
        name="DemoBrand Super Widget MODEL-100 Red",
    )
    listing = _listing(
        title="DemoBrand Super Widget MODEL-200 Red",
        brand="DemoBrand",
        model_number="MODEL-200",
    )
    result = ProductIdentityService().evaluate_product_listing(product, listing)
    assert result.decision == IdentityDecision.NO_MATCH
    assert "model_number" in result.conflicting_fields


def test_cross_size_system_does_not_hard_conflict() -> None:
    left = ProductIdentityProfile(
        category=BroadCategory.FOOTWEAR,
        model_number="RUN-1",
        size_value="10",
        size_system="US",
    )
    right = ProductIdentityProfile(
        category=BroadCategory.FOOTWEAR,
        model_number="RUN-1",
        size_value="44",
        size_system="EU",
    )
    evidence = collect_evidence(left, right)
    size_conflicts = [item for item in evidence if item.field == "size" and item.outcome.value == "CONFLICT"]
    assert not size_conflicts


def test_exact_size_conflict_requires_same_system() -> None:
    left = ProductIdentityProfile(
        category=BroadCategory.FOOTWEAR,
        model_number="RUN-1",
        brand="shoeco",
        size_value="10",
        size_system="US",
    )
    right = ProductIdentityProfile(
        category=BroadCategory.FOOTWEAR,
        model_number="RUN-1",
        brand="shoeco",
        size_value="11",
        size_system="US",
    )
    result = ProductIdentityEvaluator().evaluate(left, right, compatibility_score=50.0)
    assert result.decision == IdentityDecision.NO_MATCH
    assert "size" in result.conflicting_fields


def test_product_family_ignores_size_hard_conflict() -> None:
    left = ProductIdentityProfile(
        category=BroadCategory.FOOTWEAR,
        model_number="RUN-1",
        brand="shoeco",
        size_value="10",
        size_system="US",
    )
    right = ProductIdentityProfile(
        category=BroadCategory.FOOTWEAR,
        model_number="RUN-1",
        brand="shoeco",
        size_value="11",
        size_system="US",
    )
    result = ProductIdentityEvaluator().evaluate(
        left,
        right,
        comparison_level=IdentityComparisonLevel.PRODUCT_FAMILY,
        compatibility_score=50.0,
    )
    assert result.decision == IdentityDecision.MATCH


def test_brand_case_only_difference_not_conflict() -> None:
    left = ProductIdentityProfile(brand="DemoBrand")
    right = ProductIdentityProfile(brand="demobrand")
    evidence = collect_evidence(left, right)
    brand = next(item for item in evidence if item.field == "brand")
    assert brand.outcome.value == "AGREE"


def test_missing_brand_not_conflict() -> None:
    left = ProductIdentityProfile(brand="DemoBrand", model_number="M1")
    right = ProductIdentityProfile(brand=None, model_number="M1")
    result = ProductIdentityEvaluator().evaluate(left, right, compatibility_score=40.0)
    assert result.decision == IdentityDecision.MATCH
    assert "brand" not in result.conflicting_fields


def test_engine_keeps_insufficient_data_candidate_visible() -> None:
    product = Product(name="Demo", brand="Demo", model="M", sku="S")
    search = MarketplaceSearchResult(
        product=product,
        marketplace_name="stockx",
        selected_price_jpy=Decimal("10000"),
    )
    listing = _listing(title="Demo", brand="Demo", model_number="M")
    synthetic = ProductIdentityResult(
        decision=IdentityDecision.INSUFFICIENT_DATA,
        confidence=IdentityConfidence.UNKNOWN,
        comparison_level=IdentityComparisonLevel.EXACT_VARIANT,
        identity_score=80.0,
        hard_conflict=False,
        review_required=True,
        family_compatible=None,
        exact_variant_confirmed=None,
    )
    service = ProductIdentityService()
    with patch.object(service, "evaluate_product_listing", return_value=synthetic):
        matcher = ComparisonIdentityMatcher(identity_service=service)
        engine = ComparisonEngine(identity_matcher=matcher)
        candidate = MarketplaceCandidate(
            marketplace_name="stockx",
            search_result=search,
            price_result=PriceResult(
                product=product,
                profit_jpy=Decimal("1000"),
                profit_margin=Decimal("0.1"),
                calculation_status=CALCULATION_SUCCESS,
                domestic_sale_price_jpy=Decimal("10000"),
            ),
            listing_currency="JPY",
            source_price_amount=Decimal("10000"),
            jpy_comparable=True,
            identity_listing=listing,
        )
        result = engine.compare_product(product, [candidate])
    assert result.candidates[0].identity_result is not None
    assert result.candidates[0].identity_result.decision == IdentityDecision.INSUFFICIENT_DATA
    assert result.candidates[0].identity_matched is True


def test_excel_selected_review_identity_scope() -> None:
    product = Product(name="Demo", brand="Demo", model="M", sku="S")
    stockx_listing = _listing(listing_id="stockx-listing", title="Demo", brand="Demo", model_number="M")
    goat_listing = _listing(listing_id="goat-listing", title="Demo", brand="Demo", model_number="M")
    stockx_identity = ProductIdentityResult(
        decision=IdentityDecision.REVIEW,
        confidence=IdentityConfidence.LOW,
        comparison_level=IdentityComparisonLevel.EXACT_VARIANT,
        identity_score=40.0,
        hard_conflict=False,
        review_required=True,
        family_compatible=None,
        exact_variant_confirmed=None,
        matched_fields=("brand",),
        reasons=("partial structured evidence",),
    )
    goat_identity = ProductIdentityResult(
        decision=IdentityDecision.MATCH,
        confidence=IdentityConfidence.HIGH,
        comparison_level=IdentityComparisonLevel.EXACT_VARIANT,
        identity_score=90.0,
        hard_conflict=False,
        review_required=False,
        family_compatible=True,
        exact_variant_confirmed=True,
        matched_fields=("gtin",),
        reasons=("strong structured identity evidence supports compatibility",),
    )

    def _fake_evaluate_with_identity(product, listing, *, min_score):
        if listing is None:
            return False, None, ["no selected listing"], None
        if listing.listing_id == "stockx-listing":
            return True, Decimal("40"), [], stockx_identity
        if listing.listing_id == "goat-listing":
            return True, Decimal("90"), [], goat_identity
        return False, None, ["unknown listing"], None

    stockx = MarketplaceCandidate(
        marketplace_name="stockx",
        search_result=MarketplaceSearchResult(
            product=product,
            marketplace_name="stockx",
            selected_price_jpy=Decimal("10000"),
            selected_listing=stockx_listing,
        ),
        price_result=PriceResult(
            product=product,
            profit_jpy=Decimal("5000"),
            profit_margin=Decimal("0.5"),
            calculation_status=CALCULATION_SUCCESS,
            domestic_sale_price_jpy=Decimal("10000"),
            metadata={"data_completeness": 0.9},
            profit_intelligence=ProfitIntelligenceResult(
                overall_score=95.0,
                confidence_score=90.0,
                risk_score=10.0,
                profit_score=80.0,
                velocity_score=70.0,
                recommendation="Review",
                recommendation_stars=4,
            ),
        ),
        listing_currency="JPY",
        source_price_amount=Decimal("10000"),
        jpy_comparable=True,
        order_index=0,
        identity_listing=stockx_listing,
        identity_result=stockx_identity,
    )
    goat = MarketplaceCandidate(
        marketplace_name="goat",
        search_result=MarketplaceSearchResult(
            product=product,
            marketplace_name="goat",
            selected_price_jpy=Decimal("10000"),
            selected_listing=goat_listing,
        ),
        price_result=PriceResult(
            product=product,
            profit_jpy=Decimal("10000"),
            profit_margin=Decimal("0.8"),
            calculation_status=CALCULATION_SUCCESS,
            domestic_sale_price_jpy=Decimal("10000"),
            metadata={"data_completeness": 0.1},
        ),
        listing_currency="JPY",
        source_price_amount=Decimal("10000"),
        jpy_comparable=True,
        order_index=1,
        identity_listing=goat_listing,
        identity_result=goat_identity,
    )
    matcher = ComparisonIdentityMatcher()
    with patch.object(matcher, "evaluate_with_identity", side_effect=_fake_evaluate_with_identity):
        comparison = ComparisonEngine(identity_matcher=matcher).compare_product(product, [stockx, goat])
    row = comparison_result_to_dict(comparison)
    assert comparison.selected_review_marketplace == "stockx"
    assert comparison.highest_profit_marketplace == "goat"
    assert row["selected_review_identity_decision"] == "REVIEW"
    assert row["selected_review_identity_matched_fields"] == "brand"
    assert "selected_review_identity_decision" in MARKETPLACE_COMPARISON_COLUMNS


def test_boolean_gtin_input_rejected() -> None:
    assert build_identifier(IdentifierType.JAN, True, source_field="jan") is None
    assert build_identifier(IdentifierType.JAN, False, source_field="jan") is None


def test_integer_gtin_input_rejected() -> None:
    assert build_identifier(IdentifierType.JAN, 4006381333931, source_field="jan") is None


def test_leading_zero_preserved_in_gtin_string() -> None:
    item = build_identifier(IdentifierType.JAN, "04006381333931", source_field="jan")
    assert item is not None
    assert item.original_value == "04006381333931"


def test_select_identity_listing_skips_no_match_only() -> None:
    product = Product(brand="DemoBrand", model="MODEL-A", sku="SKU-A", name="DemoBrand Model A")
    good = _listing(listing_id="good", title="DemoBrand Model A", model_number="MODEL-A")
    bad = _listing(
        listing_id="bad",
        title="DemoBrand Model A",
        model_number="MODEL-B",
        jan_code="9780201379624",
    )
    search = MarketplaceSearchResult(
        product=product,
        marketplace_name="demo",
        listings=[good, bad],
        selected_listing=good,
    )
    selected = _select_identity_listing(
        product,
        search,
        ComparisonIdentityMatcher(),
        Decimal("30"),
    )
    assert selected is not None
    assert selected.listing_id == "good"
