"""Supplier client protocol for overseas sourcing integrations."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from supplier.models import SupplierProduct, SupplierType


@runtime_checkable
class SupplierClient(Protocol):
    """Supplier-side search contract without profit or marketplace logic."""

    @property
    def supplier_name(self) -> str:
        """Return normalized supplier identifier."""

    @property
    def supplier_type(self) -> SupplierType:
        """Return overseas supplier category."""

    def search_products(
        self,
        query: str,
        *,
        page: int = 1,
        max_results: int = 20,
    ) -> list[SupplierProduct]:
        """
        Search supplier catalog entries for a query.

        Args:
            query: Free-text product search query.
            page: 1-based page number.
            max_results: Maximum number of products to return.

        Returns:
            Supplier products in supplier-native order.
        """
