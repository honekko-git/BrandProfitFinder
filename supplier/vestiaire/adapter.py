"""Adapters between Vestiaire products and supplier models."""

from __future__ import annotations

from supplier.models import SupplierProduct, SupplierType
from supplier.vestiaire.models import VestiaireProduct


def to_supplier_product(product: VestiaireProduct) -> SupplierProduct:
    """Convert a Vestiaire product into the shared SupplierProduct model."""
    metadata = dict(product.metadata)
    if product.condition_notes:
        metadata["condition_notes"] = product.condition_notes

    return SupplierProduct(
        supplier_name="vestiaire",
        external_id=product.external_id,
        title=product.title,
        brand=product.brand,
        category=product.category,
        condition=SupplierType.USED.value,
        purchase_price=product.purchase_price,
        currency=product.currency,
        url=product.url or "",
        image_urls=[],
        availability=product.availability,
        metadata=metadata,
        model_number=product.model_number,
    )
