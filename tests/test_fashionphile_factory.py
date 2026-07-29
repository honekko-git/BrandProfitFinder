"""Tests for Fashionphile factory registration."""

from __future__ import annotations

from supplier.factory import create_supplier_client
from supplier.models import SupplierType


def test_create_supplier_client_returns_fashionphile_client() -> None:
    client = create_supplier_client("fashionphile")

    assert client is not None
    assert client.supplier_name == "fashionphile"
    assert client.supplier_type is SupplierType.USED


def test_create_supplier_client_normalizes_fashionphile_name() -> None:
    client = create_supplier_client("  Fashionphile  ")

    assert client is not None
    assert client.supplier_name == "fashionphile"
