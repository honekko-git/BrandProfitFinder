"""Supplier client adapter for imported product evaluation."""

from __future__ import annotations

from supplier.models import SupplierProduct, SupplierType


class ImportedProductSupplierClient:
    """Minimal supplier client backed by imported SupplierProduct rows."""

    def __init__(
        self,
        products: list[SupplierProduct],
        *,
        supplier_name: str = "imported",
    ) -> None:
        self._products = list(products)
        self._supplier_name = supplier_name.strip() or "imported"

    @property
    def supplier_name(self) -> str:
        return self._supplier_name

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
        normalized_query = query.strip().lower()
        if not normalized_query:
            results = self._products
        else:
            results = [
                product
                for product in self._products
                if normalized_query in product.title.lower()
                or normalized_query in product.brand.lower()
                or normalized_query in product.category.lower()
            ]
        if page < 1:
            page = 1
        start = (page - 1) * max_results
        end = start + max_results
        return results[start:end]
