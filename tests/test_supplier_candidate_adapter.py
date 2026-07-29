"""Tests for overseas new supplier candidate adapters."""

from __future__ import annotations

from supplier.models import SupplierType
from supplier.overseas_new.adapter import to_product_candidate, to_supplier_product
from supplier.overseas_new.models import OverseasNewProduct
from supplier.overseas_new.normalizer import CurrencyNormalizer


def _sample_product() -> OverseasNewProduct:
    return OverseasNewProduct(
        supplier_name="overseas_supplier",
        external_id="new-100",
        title="Gucci Marmont Mini",
        brand="Gucci",
        category="bags",
        purchase_price=300.0,
        currency="USD",
        url="https://supplier.example/new/100",
        image_urls=["https://supplier.example/new/100.jpg"],
        availability="in_stock",
        model_number="446744",
        metadata={"region": "EU"},
    )


def test_overseas_new_product_to_supplier_product() -> None:
    product = _sample_product()

    supplier_product = to_supplier_product(product)

    assert supplier_product.title == product.title
    assert supplier_product.condition == SupplierType.NEW.value
    assert supplier_product.model_number == "446744"
    assert supplier_product.metadata["region"] == "EU"


def test_overseas_new_product_to_product_candidate_with_currency_normalization() -> None:
    product = _sample_product()
    normalizer = CurrencyNormalizer(exchange_rates={"USD": 150})

    candidate = to_product_candidate(product, normalizer=normalizer)

    assert candidate["name"] == "Gucci Marmont Mini"
    assert candidate["brand"] == "Gucci"
    assert candidate["purchase_price"] == 45000.0
    assert candidate["currency"] == "JPY"
    assert candidate["source"] == "overseas_supplier"
    assert candidate["condition"] == "NEW"


def test_overseas_new_product_candidate_preserves_metadata() -> None:
    product = _sample_product()
    normalizer = CurrencyNormalizer(exchange_rates={"USD": 150})

    candidate = to_product_candidate(product, normalizer=normalizer)

    metadata = candidate["metadata"]
    assert isinstance(metadata, dict)
    assert metadata["region"] == "EU"
    assert metadata["currency_normalization"]["amount_jpy"] == 45000.0
    assert metadata["currency_normalization"]["original_amount"] == 300.0
    assert metadata["currency_normalization"]["currency"] == "USD"
