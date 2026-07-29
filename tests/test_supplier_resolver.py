"""Tests for supplier source resolver."""

from __future__ import annotations

import pytest

from supplier.adapters.source_resolver import (
    SupplierResolver,
    SupplierSourceMode,
    _LIVE_REGISTRY,
    register_live_supplier,
)
from supplier.config import SupplierRuntimeConfig
from supplier.factory import _REGISTRY, _register_default_suppliers
from supplier.fashionphile.client import FashionphileClient
from supplier.models import SupplierType


@pytest.fixture(autouse=True)
def restore_supplier_registry() -> None:
    _REGISTRY.clear()
    _register_default_suppliers()
    _LIVE_REGISTRY.clear()
    yield
    _REGISTRY.clear()
    _register_default_suppliers()
    _LIVE_REGISTRY.clear()


def test_resolver_returns_fixture_client() -> None:
    resolution = SupplierResolver(SupplierRuntimeConfig.fixture_only()).resolve("fashionphile")

    assert resolution.client is not None
    assert resolution.mode is SupplierSourceMode.FIXTURE
    assert resolution.client.supplier_name == "fashionphile"


def test_resolver_returns_none_for_unknown_supplier() -> None:
    resolution = SupplierResolver(SupplierRuntimeConfig.fixture_only()).resolve("unknown-supplier")

    assert resolution.client is None
    assert resolution.mode is None


def test_resolver_prefers_injected_client() -> None:
    injected = FashionphileClient()
    resolution = SupplierResolver(SupplierRuntimeConfig.live_only()).resolve(
        "fashionphile",
        injected_client=injected,
    )

    assert resolution.client is injected
    assert resolution.mode is None


def test_resolver_returns_none_when_live_unimplemented_and_fixture_disabled() -> None:
    resolution = SupplierResolver(SupplierRuntimeConfig.live_only()).resolve("fashionphile")

    assert resolution.client is None
    assert resolution.mode is None


def test_resolver_uses_live_client_when_registered() -> None:
    class _LiveClient:
        @property
        def supplier_name(self) -> str:
            return "fashionphile"

        @property
        def supplier_type(self) -> SupplierType:
            return SupplierType.USED

        def search_products(self, query: str, *, page: int = 1, max_results: int = 20):
            return []

    register_live_supplier("fashionphile", _LiveClient)
    resolution = SupplierResolver(SupplierRuntimeConfig.live_only()).resolve("fashionphile")

    assert resolution.client is not None
    assert resolution.mode is SupplierSourceMode.LIVE
    assert resolution.client.supplier_name == "fashionphile"
