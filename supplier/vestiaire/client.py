"""Fixture-backed Vestiaire Collective supplier client."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from supplier.base import SupplierClient
from supplier.models import SupplierProduct, SupplierType
from supplier.vestiaire.adapter import to_supplier_product
from supplier.vestiaire.models import VestiaireProduct

DEFAULT_FIXTURE_DIR = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "vestiaire"
)


class VestiaireClient:
    """Search Vestiaire Collective used inventory from local fixtures."""

    def __init__(self, *, fixture_dir: Path | str | None = None) -> None:
        self._fixture_dir = Path(fixture_dir) if fixture_dir is not None else DEFAULT_FIXTURE_DIR

    @property
    def supplier_name(self) -> str:
        return "vestiaire"

    @property
    def supplier_type(self) -> SupplierType:
        return SupplierType.USED

    def search_products(
        self,
        query: str,
        *,
        page: int = 1,
        max_results: int = 20,
    ) -> list[SupplierProduct]:
        """Search fixture-backed Vestiaire products without network access."""
        normalized_query = query.strip().lower()
        products = self._load_products()
        if normalized_query:
            products = [
                product
                for product in products
                if _matches_keyword(
                    normalized_query,
                    product.title,
                    product.brand,
                    product.category,
                )
            ]

        start = max(page - 1, 0) * max_results
        end = start + max_results
        page_products = products[start:end]
        return [to_supplier_product(product) for product in page_products]

    def _load_products(self) -> list[VestiaireProduct]:
        if not self._fixture_dir.exists():
            return []

        products: list[VestiaireProduct] = []
        for fixture_path in sorted(self._fixture_dir.glob("*.json")):
            payload = json.loads(fixture_path.read_text(encoding="utf-8"))
            items = payload.get("products", [])
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict):
                    products.append(_parse_product(item))
        return products


def _parse_product(item: dict[str, Any]) -> VestiaireProduct:
    metadata = item.get("metadata") or {}

    return VestiaireProduct(
        external_id=str(item["external_id"]),
        title=str(item["title"]),
        brand=str(item["brand"]),
        category=str(item.get("category") or ""),
        condition=str(item.get("condition") or "unknown"),
        purchase_price=float(item["purchase_price"]),
        currency=str(item.get("currency") or "USD"),
        metadata=dict(metadata) if isinstance(metadata, dict) else {},
        model_number=str(item["model_number"]) if item.get("model_number") else None,
        url=str(item["url"]) if item.get("url") else None,
        condition_notes=str(item["condition_notes"]) if item.get("condition_notes") else None,
        availability=str(item.get("availability") or "in_stock"),
    )


def _matches_keyword(query: str, *fields: str | None) -> bool:
    haystack = " ".join(field.lower() for field in fields if field)
    tokens = query.split()
    return all(token in haystack for token in tokens)
