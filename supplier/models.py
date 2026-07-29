"""Supplier intelligence models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class SupplierType(StrEnum):
    """Overseas supplier category for future sourcing integrations."""

    NEW = "NEW"
    USED = "USED"


@dataclass(slots=True)
class SupplierProduct:
    """Normalized supplier product payload independent of marketplace logic."""

    supplier_name: str
    external_id: str
    title: str
    brand: str
    category: str
    condition: str
    purchase_price: float
    currency: str
    url: str
    image_urls: list[str]
    availability: str
    metadata: dict[str, Any] = field(default_factory=dict)
    model_number: str | None = None
    jan_code: str | None = None
    sku: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize supplier product fields for tests and future adapters."""
        return asdict(self)


def to_product_candidate(product: SupplierProduct) -> dict[str, object]:
    """
    Convert a supplier product into a Product-compatible dictionary.

    Does not instantiate or mutate the existing Product model.
    """
    candidate: dict[str, object] = {
        "name": product.title,
        "brand": product.brand,
        "purchase_price": product.purchase_price,
        "currency": product.currency.upper(),
        "source": product.supplier_name,
        "category": product.category,
        "condition": product.condition,
        "url": product.url,
        "availability": product.availability,
    }
    if product.model_number is not None:
        candidate["model_number"] = product.model_number
    if product.jan_code is not None:
        candidate["jan_code"] = product.jan_code
    if product.sku is not None:
        candidate["sku"] = product.sku
    if product.image_urls:
        candidate["image_urls"] = list(product.image_urls)
    if product.metadata:
        candidate["metadata"] = dict(product.metadata)
    return candidate
