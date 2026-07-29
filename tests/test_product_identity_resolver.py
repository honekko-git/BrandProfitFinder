"""Tests for product identity resolution from discovery candidates."""

from __future__ import annotations

from product_identity.identity_resolver import ProductIdentityResolver
from profit_discovery.discovery_runner.models import DiscoveryCandidateResult, DiscoveryCandidateStatus
from supplier.models import SupplierProduct, SupplierType


def test_product_identity_resolver_normalizes_title() -> None:
    candidate = _candidate(
        title="CHANEL Classic Wallet Black Leather",
        brand="Chanel",
        category="wallets",
    )

    identity = ProductIdentityResolver().resolve(candidate)

    assert identity.normalized_name == "chanel classic wallet"
    assert identity.product_type == "Wallet"
    assert identity.brand == "Chanel"


def test_product_identity_resolver_removes_color_and_material() -> None:
    candidate = _candidate(
        title="Louis Vuitton Monogram Shoulder Bag Red Canvas Used",
        brand="Louis Vuitton",
        category="bags",
    )

    identity = ProductIdentityResolver().resolve(candidate)

    assert "red" not in identity.normalized_name
    assert "canvas" not in identity.normalized_name
    assert "used" not in identity.normalized_name
    assert identity.product_type == "Shoulder Bag"


def test_product_identity_resolver_generates_identity_key() -> None:
    candidate = _candidate(
        title="CHANEL Classic Wallet Black Leather",
        brand="Chanel",
        category="wallets",
    )

    identity = ProductIdentityResolver().resolve(candidate)

    assert identity.identity_key == "chanel_wallet"


def test_product_identity_resolver_includes_model_number_in_key() -> None:
    candidate = _candidate(
        title="CHANEL Classic Wallet Black Leather",
        brand="Chanel",
        category="wallets",
        model_number="A01112",
    )

    identity = ProductIdentityResolver().resolve(candidate)

    assert identity.model_number == "A01112"
    assert identity.identity_key == "chanel_wallet_a01112"


def _candidate(
    *,
    title: str,
    brand: str,
    category: str,
    model_number: str | None = None,
) -> DiscoveryCandidateResult:
    return DiscoveryCandidateResult(
        supplier_product=SupplierProduct(
            supplier_name="fashionphile",
            external_id="identity-resolver-001",
            title=title,
            brand=brand,
            category=category,
            condition=SupplierType.USED.value,
            purchase_price=500.0,
            currency="USD",
            url="https://example.invalid/identity-resolver-001",
            image_urls=[],
            availability="in_stock",
            model_number=model_number,
        ),
        status=DiscoveryCandidateStatus.SUCCESS,
    )
