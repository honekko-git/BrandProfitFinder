"""Tests for Vestiaire supplier adapter."""

from __future__ import annotations

from supplier.models import SupplierType
from supplier.vestiaire.adapter import to_supplier_product
from supplier.vestiaire.models import VestiaireProduct


def test_vestiaire_product_to_supplier_product() -> None:
    product = VestiaireProduct(
        external_id="vc-chanel-wallet-001",
        title="Chanel Classic Wallet Black Caviar",
        brand="Chanel",
        category="wallets",
        condition="Very Good",
        purchase_price=700.0,
        currency="USD",
        url="https://example.invalid/vestiaire/vc-chanel-wallet-001",
        model_number="VC-CH-WALLET",
        condition_notes="Minor interior wear with authentication card included.",
        metadata={"color": "black"},
    )

    supplier_product = to_supplier_product(product)

    assert supplier_product.supplier_name == "vestiaire"
    assert supplier_product.condition == SupplierType.USED.value
    assert supplier_product.brand == "Chanel"
    assert supplier_product.purchase_price == 700.0
    assert supplier_product.currency == "USD"
    assert supplier_product.model_number == "VC-CH-WALLET"
    assert supplier_product.url == product.url
    assert supplier_product.metadata["condition_notes"] == product.condition_notes
    assert supplier_product.metadata["color"] == "black"
