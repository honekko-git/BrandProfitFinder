"""Tests for TheRealReal supplier adapter."""

from __future__ import annotations

from supplier.models import SupplierType
from supplier.therealreal.adapter import to_supplier_product
from supplier.therealreal.models import TheRealRealProduct


def test_therealreal_product_to_supplier_product() -> None:
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
        condition_notes="Light exterior wear with included dust bag.",
        authentication_notes="Authenticated by The RealReal.",
        metadata={"color": "black"},
    )

    supplier_product = to_supplier_product(product)

    assert supplier_product.supplier_name == "therealreal"
    assert supplier_product.condition == SupplierType.USED.value
    assert supplier_product.brand == "Gucci"
    assert supplier_product.purchase_price == 420.0
    assert supplier_product.currency == "USD"
    assert supplier_product.model_number == "GG-MARMONT-WALLET"
    assert supplier_product.metadata["condition_notes"] == product.condition_notes
    assert supplier_product.metadata["authentication_notes"] == product.authentication_notes
    assert supplier_product.metadata["color"] == "black"
