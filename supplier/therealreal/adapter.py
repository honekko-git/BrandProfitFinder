"""Adapters between TheRealReal products and supplier models."""

from __future__ import annotations

from supplier.models import SupplierProduct, SupplierType
from supplier.therealreal.models import TheRealRealProduct


def to_supplier_product(product: TheRealRealProduct) -> SupplierProduct:
    """Convert a TheRealReal product into the shared SupplierProduct model."""
    metadata = dict(product.metadata)
    if product.condition_notes:
        metadata["condition_notes"] = product.condition_notes
    if product.authentication_notes:
        metadata["authentication_notes"] = product.authentication_notes

    return SupplierProduct(
        supplier_name="therealreal",
        external_id=product.external_id,
        title=product.title,
        brand=product.brand,
        category=product.category,
        condition=SupplierType.USED.value,
        purchase_price=product.purchase_price,
        currency=product.currency,
        url=product.url,
        image_urls=list(product.image_urls),
        availability=product.availability,
        metadata=metadata,
        model_number=product.model_number,
    )
