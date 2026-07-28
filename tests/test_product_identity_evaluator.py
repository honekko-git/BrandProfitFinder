"""Tests for product identity evaluator."""

import copy
import json
from decimal import Decimal
from pathlib import Path

import pytest

from models.marketplace_listing import MarketplaceListing
from models.product import Product
from product_identity.adapter import ProductIdentityService
from product_identity.enums import IdentityDecision
from product_identity.evaluator import ProductIdentityEvaluator
from product_identity.extractor import extract_from_listing, extract_from_product

FIXTURE = Path(__file__).parent / "fixtures" / "product_identity_phase19.json"


def _load_pair(pair_id: str) -> tuple[Product, MarketplaceListing, str]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for item in payload["pairs"]:
        if item["id"] == pair_id:
            product = Product(**item["product"])
            listing_data = dict(item["listing"])
            meta = listing_data.pop("source_metadata", {})
            price = Decimal(str(listing_data.pop("price_jpy", 0)))
            listing = MarketplaceListing(
                **listing_data,
                price_jpy=price,
                source_metadata=meta,
            )
            return product, listing, item["expected_decision"]
    raise KeyError(pair_id)


@pytest.mark.parametrize(
    "pair_id",
    [
        "A_matching_jan",
        "B_conflicting_jan",
        "C_matching_model",
        "D_brand_conflict",
        "F_title_only",
        "G_insufficient",
    ],
)
def test_fixture_expected_decisions(pair_id: str) -> None:
    product, listing, expected = _load_pair(pair_id)
    service = ProductIdentityService()
    result = service.evaluate_product_listing(product, listing)
    assert result.decision.value == expected


def test_no_match_excluded_from_comparison_matcher() -> None:
    from comparison.matcher import ComparisonIdentityMatcher

    product, listing, _ = _load_pair("B_conflicting_jan")
    eligible, score, warnings, identity_result = ComparisonIdentityMatcher().evaluate_with_identity(
        product, listing, min_score=Decimal("30")
    )
    assert identity_result is not None
    assert identity_result.decision == IdentityDecision.NO_MATCH
    assert eligible is False


def test_evaluate_three_tuple_historical_unpacking() -> None:
    from comparison.matcher import ComparisonIdentityMatcher

    product, listing, _ = _load_pair("C_matching_model")
    is_match, score, warnings = ComparisonIdentityMatcher().evaluate(
        product, listing, min_score=Decimal("30")
    )
    assert isinstance(is_match, bool)
    assert score is not None
    assert isinstance(warnings, list)


def test_extraction_does_not_mutate_listing() -> None:
    product, listing, _ = _load_pair("C_matching_model")
    snapshot = copy.deepcopy(listing)
    extract_from_listing(listing)
    extract_from_product(product)
    assert listing == snapshot


def test_repeatable_evaluation() -> None:
    product, listing, _ = _load_pair("A_matching_jan")
    service = ProductIdentityService()
    first = service.evaluate_product_listing(product, listing)
    second = service.evaluate_product_listing(product, listing)
    assert first.decision == second.decision
    assert first.reasons == second.reasons
