"""Adapters between Fashionphile products and supplier models."""

from __future__ import annotations

from typing import Any

from supplier.fashionphile.models import FashionphileProduct
from supplier.live.models import SupplierLiveResponse
from supplier.models import SupplierProduct, SupplierType


def to_supplier_product(product: FashionphileProduct) -> SupplierProduct:
    """Convert a Fashionphile product into the shared SupplierProduct model."""
    metadata = dict(product.metadata)
    if product.condition_notes:
        metadata["condition_notes"] = product.condition_notes
    if product.authentication:
        metadata["authentication"] = dict(product.authentication)

    return SupplierProduct(
        supplier_name="fashionphile",
        external_id=product.external_id,
        title=product.title,
        brand=product.brand,
        category=product.category,
        condition=SupplierType.USED.value,
        purchase_price=product.price,
        currency=product.currency.upper(),
        url=product.url,
        image_urls=list(product.image_urls),
        availability=product.availability,
        metadata=metadata,
        model_number=product.model_number,
    )


def live_response_to_supplier_products(response: SupplierLiveResponse) -> list[SupplierProduct]:
    """Convert a live Fashionphile response payload into supplier products."""
    items = response.payload.get("products") or response.payload.get("items") or []
    if not isinstance(items, list):
        return []

    products: list[SupplierProduct] = []
    for item in items:
        if isinstance(item, dict):
            products.append(to_supplier_product(_parse_live_item(item)))
    return products


def _parse_live_item(item: dict[str, Any]) -> FashionphileProduct:
    image_urls = item.get("image_urls") or []
    if not isinstance(image_urls, list):
        image_urls = [str(image_urls)]

    metadata = item.get("metadata") or {}
    authentication = item.get("authentication")
    if authentication is not None and not isinstance(authentication, dict):
        authentication = {"status": str(authentication)}

    purchase_price = item.get("purchase_price", item.get("price"))
    return FashionphileProduct(
        external_id=str(item["external_id"]),
        title=str(item["title"]),
        brand=str(item["brand"]),
        category=str(item.get("category") or ""),
        condition=str(item.get("condition") or "unknown"),
        price=float(purchase_price),
        currency=str(item.get("currency") or "USD").upper(),
        url=str(item.get("url") or ""),
        image_urls=[str(url) for url in image_urls],
        metadata=dict(metadata) if isinstance(metadata, dict) else {},
        model_number=str(item["model_number"]) if item.get("model_number") else None,
        condition_notes=str(item["condition_notes"]) if item.get("condition_notes") else None,
        authentication=dict(authentication) if isinstance(authentication, dict) else None,
        availability=str(item.get("availability") or "in_stock"),
    )
