"""Tests for Vestiaire supplier models."""

from __future__ import annotations

from supplier.vestiaire.models import VestiaireProduct


def test_vestiaire_product_creation() -> None:
    product = VestiaireProduct(
        external_id="vc-hermes-bag-001",
        title="Hermes Evelyne III PM Gold",
        brand="Hermes",
        category="bags",
        condition="Good",
        purchase_price=3200.0,
        currency="USD",
        model_number="EVELYNE-III-PM",
        url="https://example.invalid/vestiaire/vc-hermes-bag-001",
        condition_notes="Visible corner wear.",
    )

    assert product.external_id == "vc-hermes-bag-001"
    assert product.brand == "Hermes"
    assert product.purchase_price == 3200.0


def test_vestiaire_product_optional_fields() -> None:
    product = VestiaireProduct(
        external_id="vc-chanel-wallet-001",
        title="Chanel Classic Wallet",
        brand="Chanel",
        category="wallets",
        condition="Very Good",
        purchase_price=700.0,
        currency="USD",
        metadata={"color": "black"},
    )

    assert product.model_number is None
    assert product.url is None
    assert product.condition_notes is None
    assert product.metadata["color"] == "black"


def test_vestiaire_product_serialization() -> None:
    product = VestiaireProduct(
        external_id="vc-lv-bag-001",
        title="Louis Vuitton Neverfull MM Damier Ebene",
        brand="Louis Vuitton",
        category="bags",
        condition="Very Good",
        purchase_price=1450.0,
        currency="USD",
        url="https://example.invalid/vestiaire/vc-lv-bag-001",
    )

    payload = product.to_dict()

    assert payload["brand"] == "Louis Vuitton"
    assert payload["purchase_price"] == 1450.0
