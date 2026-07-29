"""Tests for TheRealReal supplier models."""

from __future__ import annotations

from supplier.therealreal.models import TheRealRealProduct


def test_therealreal_product_creation() -> None:
    product = TheRealRealProduct(
        external_id="trr-gucci-wallet-001",
        title="Gucci GG Marmont Wallet Black",
        brand="Gucci",
        category="wallets",
        condition="Very Good",
        purchase_price=420.0,
        currency="USD",
        url="https://example.invalid/therealreal/trr-gucci-wallet-001",
        image_urls=["https://example.invalid/images/therealreal/trr-gucci-wallet-001.jpg"],
        model_number="GG-MARMONT-WALLET",
        condition_notes="Light exterior wear.",
        authentication_notes="Authenticated by The RealReal.",
    )

    assert product.external_id == "trr-gucci-wallet-001"
    assert product.brand == "Gucci"
    assert product.purchase_price == 420.0


def test_therealreal_product_optional_fields() -> None:
    product = TheRealRealProduct(
        external_id="trr-chanel-wallet-001",
        title="Chanel Classic Wallet",
        brand="Chanel",
        category="wallets",
        condition="Very Good",
        purchase_price=700.0,
        currency="USD",
        url="https://example.invalid/therealreal/trr-chanel-wallet-001",
        image_urls=[],
        metadata={"color": "black"},
    )

    assert product.model_number is None
    assert product.authentication_notes is None
    assert product.metadata["color"] == "black"


def test_therealreal_product_serialization() -> None:
    product = TheRealRealProduct(
        external_id="trr-lv-bag-001",
        title="Louis Vuitton Neverfull MM Damier Ebene",
        brand="Louis Vuitton",
        category="bags",
        condition="Very Good",
        purchase_price=1450.0,
        currency="USD",
        url="https://example.invalid/therealreal/trr-lv-bag-001",
        image_urls=["https://example.invalid/images/therealreal/trr-lv-bag-001.jpg"],
    )

    payload = product.to_dict()

    assert payload["brand"] == "Louis Vuitton"
    assert payload["purchase_price"] == 1450.0
