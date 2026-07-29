"""Overseas new supplier client protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from supplier.models import SupplierProduct


@runtime_checkable
class OverseasNewSupplierClient(Protocol):
    """Overseas new supplier search contract without profit or marketplace logic."""

    @property
    def supplier_name(self) -> str:
        """Return normalized overseas new supplier identifier."""

    def search_products(
        self,
        query: str,
        *,
        page: int = 1,
        max_results: int = 20,
    ) -> list[SupplierProduct]:
        """
        Search overseas new catalog entries for a query.

        Args:
            query: Free-text product search query.
            page: 1-based page number.
            max_results: Maximum number of products to return.

        Returns:
            Supplier products in supplier-native order.
        """
