"""Adapters between overseas new products and supplier/product boundaries."""

from __future__ import annotations

from supplier.models import SupplierProduct, SupplierType, to_product_candidate as supplier_to_product_candidate
from supplier.overseas_new.models import OverseasNewProduct
from supplier.overseas_new.normalizer import CurrencyNormalizer


def to_supplier_product(product: OverseasNewProduct) -> SupplierProduct:
    """Convert an overseas new product into the shared SupplierProduct model."""
    return SupplierProduct(
        supplier_name=product.supplier_name,
        external_id=product.external_id,
        title=product.title,
        brand=product.brand,
        category=product.category,
        condition=SupplierType.NEW.value,
        purchase_price=product.purchase_price,
        currency=product.currency.upper(),
        url=product.url,
        image_urls=list(product.image_urls),
        availability=product.availability,
        metadata=dict(product.metadata),
        model_number=product.model_number,
        jan_code=product.jan_code,
    )


def to_product_candidate(
    product: OverseasNewProduct,
    *,
    normalizer: CurrencyNormalizer | None = None,
) -> dict[str, object]:
    """
    Convert an overseas new product into a Product-compatible dictionary.

    Does not instantiate or mutate the existing Product model.
    """
    supplier_product = to_supplier_product(product)
    candidate = supplier_to_product_candidate(supplier_product)

    if normalizer is None:
        return candidate

    normalized = normalizer.normalize(product.purchase_price, product.currency)
    candidate["purchase_price"] = normalized.amount_jpy if normalized.amount_jpy is not None else product.purchase_price
    candidate["currency"] = "JPY" if normalized.amount_jpy is not None else normalized.currency
    candidate["original_purchase_price"] = normalized.original_amount
    candidate["original_currency"] = normalized.currency
    candidate["metadata"] = {
        **dict(candidate.get("metadata", {})),
        "currency_normalization": {
            "amount_jpy": normalized.amount_jpy,
            "original_amount": normalized.original_amount,
            "currency": normalized.currency,
        },
    }
    return candidate
