"""Supplier client factory for future overseas sourcing integrations."""

from __future__ import annotations

from supplier.base import SupplierClient


def create_supplier_client(name: str) -> SupplierClient | None:
    """
    Resolve a supplier client by name.

    Future supplier implementations will register here. No live supplier
    integrations are wired in this phase.
    """
    normalized = name.strip().lower()
    if not normalized:
        return None

    # Extension point for future suppliers such as overseas new/used sources.
    _ = normalized
    return None
