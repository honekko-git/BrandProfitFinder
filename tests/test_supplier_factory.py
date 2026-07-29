"""Tests for supplier factory extension point."""

from __future__ import annotations

import pytest

from supplier.factory import create_supplier_client


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
