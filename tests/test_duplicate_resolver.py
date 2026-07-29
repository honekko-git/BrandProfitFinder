"""Tests for duplicate candidate merging by product identity."""

from __future__ import annotations

from decimal import Decimal

from models.price_result import PriceResult
from models.product import Product
from product_identity.duplicate_resolver import DuplicateResolver
from profit_discovery.discovery_runner.models import DiscoveryCandidateResult, DiscoveryCandidateStatus
from profit_discovery.market_connector.models import MarketEvaluationResult
from supplier.models import SupplierProduct, SupplierType


def test_duplicate_resolver_merges_same_identity_candidates() -> None:
    candidates = [
        _candidate(
            external_id="dup-001",
            title="CHANEL Classic Wallet Black Leather",
            profit_jpy=10000.0,
            confidence_score=0.7,
        ),
        _candidate(
            external_id="dup-002",
            title="Chanel Wallet Red Caviar Used",
            profit_jpy=15000.0,
            confidence_score=0.5,
        ),
    ]

    merged = DuplicateResolver().merge_candidates(candidates)

    assert len(merged) == 1
    assert merged[0].supplier_product.external_id == "dup-002"
    assert merged[0].metadata["identity_key"] == "chanel_wallet"
    assert merged[0].metadata["merged_candidate_count"] == 2
    assert set(merged[0].metadata["merged_external_ids"]) == {"dup-001", "dup-002"}
    assert merged[0].metadata["best_market_confidence"] == 0.7


def test_duplicate_resolver_keeps_different_brands_separate() -> None:
    candidates = [
        _candidate(
            external_id="brand-001",
            title="CHANEL Classic Wallet Black Leather",
            brand="Chanel",
            profit_jpy=12000.0,
        ),
        _candidate(
            external_id="brand-002",
            title="Louis Vuitton Wallet Black Leather",
            brand="Louis Vuitton",
            profit_jpy=11000.0,
        ),
    ]

    merged = DuplicateResolver().merge_candidates(candidates)

    assert len(merged) == 2
    external_ids = {candidate.supplier_product.external_id for candidate in merged}
    assert external_ids == {"brand-001", "brand-002"}


def test_duplicate_resolver_keeps_different_products_separate() -> None:
    candidates = [
        _candidate(
            external_id="product-001",
            title="CHANEL Classic Wallet Black Leather",
            category="wallets",
            profit_jpy=12000.0,
        ),
        _candidate(
            external_id="product-002",
            title="CHANEL Classic Shoulder Bag Black Leather",
            category="bags",
            profit_jpy=13000.0,
        ),
    ]

    merged = DuplicateResolver().merge_candidates(candidates)

    assert len(merged) == 2
    identity_keys = {candidate.metadata["identity_key"] for candidate in merged}
    assert identity_keys == {"chanel_wallet", "chanel_shoulder_bag"}


def _candidate(
    *,
    external_id: str,
    title: str,
    profit_jpy: float,
    brand: str = "Chanel",
    category: str = "wallets",
    confidence_score: float = 0.8,
) -> DiscoveryCandidateResult:
    product = SupplierProduct(
        supplier_name="fashionphile",
        external_id=external_id,
        title=title,
        brand=brand,
        category=category,
        condition=SupplierType.USED.value,
        purchase_price=500.0,
        currency="USD",
        url=f"https://example.invalid/{external_id}",
        image_urls=[],
        availability="in_stock",
    )
    return DiscoveryCandidateResult(
        supplier_product=product,
        status=DiscoveryCandidateStatus.SUCCESS,
        profit_result=PriceResult(
            product=Product(name=title, brand=brand, price=500.0, currency="USD"),
            profit_jpy=Decimal(str(profit_jpy)),
            profit_margin=Decimal("30.0"),
            roi=Decimal("55.0"),
            calculation_status="success",
        ),
        market_evaluation=MarketEvaluationResult(
            supplier_product_id=external_id,
            domestic_market_price=None,
            matched_keyword=f"{brand} wallet",
            confidence_score=confidence_score,
        ),
    )
