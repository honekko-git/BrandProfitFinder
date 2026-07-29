"""Tests for supplier factory extension point."""

from __future__ import annotations

import pytest

from supplier.base import SupplierClient
from supplier.factory import _REGISTRY, _register_default_suppliers, create_supplier_client, register_supplier
from supplier.models import SupplierType


@pytest.fixture(autouse=True)
def clear_supplier_registry() -> None:
    _REGISTRY.clear()
    _register_default_suppliers()
    yield
    _REGISTRY.clear()


def test_unknown_supplier_returns_none() -> None:
    assert create_supplier_client("unknown-supplier") is None


def test_blank_supplier_name_returns_none() -> None:
    assert create_supplier_client("") is None
    assert create_supplier_client("   ") is None


def test_factory_normalizes_supplier_name_for_future_registration() -> None:
    # Future suppliers will register against normalized names.
    assert create_supplier_client("  Future-Supplier  ") is None


@pytest.mark.parametrize(
    "supplier_name",
    [
        "overseas-new",
        "overseas-used",
        "sample-supplier",
    ],
)
def test_unregistered_suppliers_remain_unimplemented(supplier_name: str) -> None:
    assert create_supplier_client(supplier_name) is None


def test_register_supplier_enables_factory_resolution() -> None:
    class _RegisteredClient:
        @property
        def supplier_name(self) -> str:
            return "overseas-new"

        @property
        def supplier_type(self) -> SupplierType:
            return SupplierType.NEW

        def search_products(self, query: str, *, page: int = 1, max_results: int = 20):
            return []

    register_supplier("Overseas-New", lambda: _RegisteredClient())

    client = create_supplier_client("overseas-new")

    assert client is not None
    assert client.supplier_name == "overseas-new"
