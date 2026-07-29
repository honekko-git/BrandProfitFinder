"""Tests for Fashionphile live response adapter."""

from __future__ import annotations

from supplier.fashionphile.adapter import live_response_to_supplier_products, to_supplier_product
from supplier.fashionphile.models import FashionphileProduct
from supplier.live.models import SupplierLiveResponse
from supplier.models import SupplierType


def test_live_response_adapter_builds_supplier_products() -> None:
    response = SupplierLiveResponse(
        supplier_name="fashionphile",
        status_code=200,
        payload={
            "products": [
                {
                    "external_id": "fp-live-001",
                    "title": "Chanel Classic Wallet Black Caviar",
                    "brand": "Chanel",
                    "category": "wallets",
                    "condition": "Very Good",
                    "purchase_price": 700.0,
                    "currency": "USD",
                    "url": "https://example.invalid/fashionphile/fp-live-001",
                    "image_urls": ["https://example.invalid/images/fp-live-001.jpg"],
                    "model_number": "CH-WALLET",
                    "condition_notes": "Minor interior wear.",
                    "authentication": {"status": "authenticated"},
                    "availability": "in_stock",
                    "metadata": {"color": "black"},
                }
            ]
        },
    )

    products = live_response_to_supplier_products(response)

    assert len(products) == 1
    assert products[0].supplier_name == "fashionphile"
    assert products[0].external_id == "fp-live-001"
    assert products[0].brand == "Chanel"
    assert products[0].purchase_price == 700.0
    assert products[0].condition == SupplierType.USED.value
    assert products[0].metadata["authentication"]["status"] == "authenticated"


def test_live_response_adapter_matches_fixture_adapter_shape() -> None:
    item = {
        "external_id": "fp-live-002",
        "title": "Gucci Wallet",
        "brand": "Gucci",
        "category": "wallets",
        "condition": "Very Good",
        "price": 420.0,
        "currency": "USD",
        "url": "https://example.invalid/fashionphile/fp-live-002",
        "image_urls": [],
        "availability": "in_stock",
    }
    live_products = live_response_to_supplier_products(
        SupplierLiveResponse(
            supplier_name="fashionphile",
            status_code=200,
            payload={"items": [item]},
        )
    )
    fixture_product = to_supplier_product(
        FashionphileProduct(
            external_id="fp-live-002",
            title="Gucci Wallet",
            brand="Gucci",
            category="wallets",
            condition="Very Good",
            price=420.0,
            currency="USD",
            url="https://example.invalid/fashionphile/fp-live-002",
            image_urls=[],
        )
    )

    assert live_products[0].supplier_name == fixture_product.supplier_name
    assert live_products[0].external_id == fixture_product.external_id
    assert live_products[0].purchase_price == fixture_product.purchase_price
    assert live_products[0].currency == fixture_product.currency
