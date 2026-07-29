"""Tests for supplier product models."""

from __future__ import annotations

from supplier.models import SupplierProduct, SupplierType, to_product_candidate


def test_supplier_product_creation_with_required_fields() -> None:
    product = SupplierProduct(
        supplier_name="sample-supplier",
        external_id="item-001",
        title="Gucci Marmont Bag",
        brand="Gucci",
        category="bags",
        condition="new",
        purchase_price=980.0,
        currency="USD",
        url="https://supplier.example/items/item-001",
        image_urls=["https://supplier.example/images/item-001.jpg"],
        availability="in_stock",
    )

    assert product.supplier_name == "sample-supplier"
    assert product.external_id == "item-001"
    assert product.title == "Gucci Marmont Bag"
    assert product.purchase_price == 980.0
    assert product.currency == "USD"
    assert product.availability == "in_stock"


def test_supplier_product_optional_fields() -> None:
    product = SupplierProduct(
        supplier_name="used-supplier",
        external_id="used-42",
        title="Used Chanel Flap",
        brand="Chanel",
        category="bags",
        condition="used",
        purchase_price=1200.0,
        currency="EUR",
        url="https://supplier.example/used/42",
        image_urls=[],
        availability="limited",
        model_number="A01112",
        jan_code="4901234567890",
        sku="CH-FLAP-42",
        metadata={"supplier_type": SupplierType.USED.value},
    )

    assert product.model_number == "A01112"
    assert product.jan_code == "4901234567890"
    assert product.sku == "CH-FLAP-42"
    assert product.metadata["supplier_type"] == "USED"


def test_supplier_product_serialization() -> None:
    product = SupplierProduct(
        supplier_name="sample-supplier",
        external_id="item-002",
        title="Prada Re-Edition",
        brand="Prada",
        category="bags",
        condition="new",
        purchase_price=650.0,
        currency="USD",
        url="https://supplier.example/items/item-002",
        image_urls=["https://supplier.example/images/item-002.jpg"],
        availability="in_stock",
        sku="PR-RE-002",
    )

    payload = product.to_dict()

    assert payload["supplier_name"] == "sample-supplier"
    assert payload["sku"] == "PR-RE-002"
    assert payload["image_urls"] == ["https://supplier.example/images/item-002.jpg"]


def test_to_product_candidate_returns_product_compatible_dict() -> None:
    product = SupplierProduct(
        supplier_name="sample-supplier",
        external_id="item-003",
        title="Dior Saddle Bag",
        brand="Dior",
        category="bags",
        condition="new",
        purchase_price=890.0,
        currency="usd",
        url="https://supplier.example/items/item-003",
        image_urls=["https://supplier.example/images/item-003.jpg"],
        availability="in_stock",
        model_number="M001",
    )

    candidate = to_product_candidate(product)

    assert candidate == {
        "name": "Dior Saddle Bag",
        "brand": "Dior",
        "purchase_price": 890.0,
        "currency": "USD",
        "source": "sample-supplier",
        "category": "bags",
        "condition": "new",
        "url": "https://supplier.example/items/item-003",
        "availability": "in_stock",
        "model_number": "M001",
        "image_urls": ["https://supplier.example/images/item-003.jpg"],
    }
