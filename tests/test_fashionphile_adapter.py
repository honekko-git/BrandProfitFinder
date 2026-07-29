"""Tests for Fashionphile supplier adapter."""

from __future__ import annotations

from supplier.fashionphile.adapter import to_supplier_product
from supplier.fashionphile.models import FashionphileProduct
from supplier.models import SupplierType


def test_fashionphile_product_to_supplier_product() -> None:
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
        condition_notes="Light exterior wear with included dust bag.",
        authentication={
            "status": "authenticated",
            "provider": "Fashionphile",
            "platform_authenticated": True,
        },
        metadata={"color": "black"},
    )

    supplier_product = to_supplier_product(product)

    assert supplier_product.supplier_name == "fashionphile"
    assert supplier_product.condition == SupplierType.USED.value
    assert supplier_product.brand == "Gucci"
    assert supplier_product.model_number == "GG-MARMONT"
    assert supplier_product.url == product.url
    assert supplier_product.metadata["condition_notes"] == product.condition_notes
    assert supplier_product.metadata["authentication"]["provider"] == "Fashionphile"
    assert supplier_product.metadata["color"] == "black"
