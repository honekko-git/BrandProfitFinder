"""Tests for Fashionphile supplier models."""

from __future__ import annotations

from supplier.fashionphile.models import FashionphileProduct


def test_fashionphile_product_creation() -> None:
    product = FashionphileProduct(
        external_id="fp-gucci-001",
        title="Gucci GG Marmont Small Shoulder Bag Black",
        brand="Gucci",
        category="bags",
        condition="Very Good",
        price=980.0,
        currency="USD",
        url="https://example.invalid/fashionphile/fp-gucci-001",
        image_urls=["https://example.invalid/images/fashionphile/fp-gucci-001.jpg"],
        model_number="GG-MARMONT",
        condition_notes="Light exterior wear.",
        authentication={"status": "authenticated", "provider": "Fashionphile"},
    )

    assert product.external_id == "fp-gucci-001"
    assert product.brand == "Gucci"
    assert product.price == 980.0


def test_fashionphile_product_optional_fields() -> None:
    product = FashionphileProduct(
        external_id="fp-chanel-001",
        title="Chanel Classic Flap",
        brand="Chanel",
        category="bags",
        condition="Excellent",
        price=5200.0,
        currency="USD",
        url="https://example.invalid/fashionphile/fp-chanel-001",
        image_urls=[],
        metadata={"color": "black"},
    )

    assert product.model_number is None
    assert product.metadata["color"] == "black"


def test_fashionphile_product_serialization() -> None:
    product = FashionphileProduct(
        external_id="fp-hermes-001",
        title="Hermes Evelyne III PM Gold",
        brand="Hermes",
        category="bags",
        condition="Good",
        price=3200.0,
        currency="USD",
        url="https://example.invalid/fashionphile/fp-hermes-001",
        image_urls=["https://example.invalid/images/fashionphile/fp-hermes-001.jpg"],
    )

    payload = product.to_dict()

    assert payload["brand"] == "Hermes"
    assert payload["price"] == 3200.0
