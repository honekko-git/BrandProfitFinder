"""Supplier client factory for future overseas sourcing integrations."""

from __future__ import annotations

from collections.abc import Callable

from supplier.base import SupplierClient

SupplierFactory = Callable[[], SupplierClient]

_REGISTRY: dict[str, SupplierFactory] = {}


def register_supplier(name: str, factory: SupplierFactory) -> None:
    """
    Register a supplier client factory for future integrations.

    Registration is an extension point only; no live clients are wired here.
    """
    normalized = _normalize_supplier_name(name)
    if not normalized:
        raise ValueError("supplier name must not be blank")
    _REGISTRY[normalized] = factory


def create_supplier_client(name: str) -> SupplierClient | None:
    """
    Resolve a supplier client by name.

    Returns None when the supplier is unknown or not yet registered.
    """
    normalized = _normalize_supplier_name(name)
    if not normalized:
        return None

    factory = _REGISTRY.get(normalized)
    if factory is None:
        return None
    return factory()


def _normalize_supplier_name(name: str) -> str:
    return name.strip().lower()


def _register_default_suppliers() -> None:
    from supplier.fashionphile.client import FashionphileClient

    register_supplier("fashionphile", FashionphileClient)


_register_default_suppliers()
