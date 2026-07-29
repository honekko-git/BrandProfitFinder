"""Tests for Vestiaire factory registration."""

from __future__ import annotations

import pytest

from supplier.factory import _REGISTRY, _register_default_suppliers, create_supplier_client
from supplier.models import SupplierType


@pytest.fixture(autouse=True)
def restore_supplier_registry() -> None:
    _REGISTRY.clear()
    _register_default_suppliers()
    yield
    _REGISTRY.clear()
    _register_default_suppliers()


def test_create_supplier_client_returns_vestiaire_client() -> None:
    client = create_supplier_client("vestiaire")

    assert client is not None
    assert client.supplier_name == "vestiaire"
    assert client.supplier_type is SupplierType.USED


def test_create_supplier_client_normalizes_vestiaire_name() -> None:
    client = create_supplier_client("  Vestiaire  ")

    assert client is not None
    assert client.supplier_name == "vestiaire"
