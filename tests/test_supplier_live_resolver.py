"""Tests for live supplier resolver."""

from __future__ import annotations

import pytest

from supplier.factory import _REGISTRY, _register_default_suppliers
from supplier.fashionphile.client import FashionphileClient
from supplier.live.resolver import (
    LiveSupplierResolver,
    LiveSupplierSourceMode,
    _LIVE_REGISTRY,
    register_live_supplier_client,
)
from supplier.models import SupplierType


@pytest.fixture(autouse=True)
def restore_supplier_registries() -> None:
    _REGISTRY.clear()
    _register_default_suppliers()
    _LIVE_REGISTRY.clear()
    yield
    _REGISTRY.clear()
    _register_default_suppliers()
    _LIVE_REGISTRY.clear()


def test_live_resolver_prefers_injected_client() -> None:
    injected = FashionphileClient()
    resolution = LiveSupplierResolver().resolve(
        "fashionphile",
        injected_client=injected,
    )

    assert resolution.client is injected
    assert resolution.mode is None


def test_live_resolver_uses_live_client_when_registered() -> None:
    class _LiveFashionphileClient:
        @property
        def supplier_name(self) -> str:
            return "fashionphile"

        @property
        def supplier_type(self) -> SupplierType:
            return SupplierType.USED

        def search_products(self, query: str, *, page: int = 1, max_results: int = 20):
            _ = query, page, max_results
            return []

    register_live_supplier_client("fashionphile", _LiveFashionphileClient)
    resolution = LiveSupplierResolver().resolve("fashionphile")

    assert resolution.client is not None
    assert resolution.mode is LiveSupplierSourceMode.LIVE
    assert resolution.client.supplier_name == "fashionphile"


def test_live_resolver_falls_back_to_fixture_when_live_missing() -> None:
    resolution = LiveSupplierResolver().resolve("fashionphile")

    assert resolution.client is not None
    assert resolution.mode is LiveSupplierSourceMode.FIXTURE
    assert resolution.client.supplier_name == "fashionphile"


def test_live_resolver_returns_none_for_unknown_supplier() -> None:
    resolution = LiveSupplierResolver().resolve("unknown-supplier")

    assert resolution.client is None
    assert resolution.mode is None
