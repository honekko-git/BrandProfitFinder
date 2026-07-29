"""Tests for demand query resolution from discovery candidates."""

from __future__ import annotations

from profit_discovery.discovery_runner.models import DiscoveryCandidateResult, DiscoveryCandidateStatus
from profit_intelligence.demand import DemandQueryResolver
from supplier.models import SupplierProduct, SupplierType


def test_demand_query_resolver_extracts_brand_and_wallet_type() -> None:
    candidate = _candidate(
        title="CHANEL Classic Wallet Black Leather",
        brand="Chanel",
        category="wallets",
    )

    query = DemandQueryResolver().resolve(candidate)

    assert query.brand == "Chanel"
    assert query.product_type == "Wallet"
    assert query.normalized_query == "Chanel Wallet"


def test_demand_query_resolver_strips_noise_words_for_shoulder_bag() -> None:
    candidate = _candidate(
        title="Louis Vuitton Monogram Shoulder Bag",
        brand="Louis Vuitton",
        category="bags",
    )

    query = DemandQueryResolver().resolve(candidate)

    assert query.brand == "Louis Vuitton"
    assert query.product_type == "Shoulder Bag"
    assert query.normalized_query == "Louis Vuitton Shoulder Bag"


def test_demand_query_resolver_uses_category_when_title_has_no_type() -> None:
    candidate = _candidate(
        title="Coach Logo Item Red Canvas",
        brand="Coach",
        category="wallets",
    )

    query = DemandQueryResolver().resolve(candidate)

    assert query.product_type == "Wallet"
    assert query.normalized_query == "Coach Wallet"


def _candidate(*, title: str, brand: str, category: str) -> DiscoveryCandidateResult:
    return DiscoveryCandidateResult(
        supplier_product=SupplierProduct(
            supplier_name="fashionphile",
            external_id="demand-query-001",
            title=title,
            brand=brand,
            category=category,
            condition=SupplierType.USED.value,
            purchase_price=500.0,
            currency="USD",
            url="https://example.invalid/demand-query-001",
            image_urls=[],
            availability="in_stock",
        ),
        status=DiscoveryCandidateStatus.SUCCESS,
    )
