"""Tests for overseas new supplier models."""

from __future__ import annotations

from supplier.overseas_new.models import OverseasNewProduct


def test_overseas_new_product_creation_with_required_fields() -> None:
    product = OverseasNewProduct(
        supplier_name="overseas-supplier",
        external_id="new-001",
        title="Gucci Marmont Small",
        brand="Gucci",
        category="bags",
        purchase_price=980.0,
        currency="USD",
        url="https://supplier.example/new/001",
        image_urls=["https://supplier.example/new/001.jpg"],
        availability="in_stock",
    )

    assert product.supplier_name == "overseas-supplier"
    assert product.external_id == "new-001"
    assert product.title == "Gucci Marmont Small"
    assert product.purchase_price == 980.0
    assert product.currency == "USD"


def test_overseas_new_product_optional_fields() -> None:
    product = OverseasNewProduct(
        supplier_name="overseas-supplier",
        external_id="new-002",
        title="Prada Re-Edition",
        brand="Prada",
        category="bags",
        purchase_price=650.0,
        currency="EUR",
        url="https://supplier.example/new/002",
        image_urls=[],
        availability="limited",
        model_number="1BH204",
        jan_code="4901234567891",
        metadata={"collection": "re-edition"},
    )

    assert product.model_number == "1BH204"
    assert product.jan_code == "4901234567891"
    assert product.metadata["collection"] == "re-edition"


def test_overseas_new_product_serialization() -> None:
    product = OverseasNewProduct(
        supplier_name="overseas-supplier",
        external_id="new-003",
        title="Dior Book Tote",
        brand="Dior",
        category="bags",
        purchase_price=890.0,
        currency="USD",
        url="https://supplier.example/new/003",
        image_urls=["https://supplier.example/new/003.jpg"],
        availability="in_stock",
    )

    payload = product.to_dict()

    assert payload["external_id"] == "new-003"
    assert payload["availability"] == "in_stock"
