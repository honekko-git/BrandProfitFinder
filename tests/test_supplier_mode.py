"""Tests for supplier runtime configuration."""

from __future__ import annotations

import pytest

from supplier.config import SupplierRuntimeConfig
from supplier.factory import _REGISTRY, _register_default_suppliers, resolve_supplier_client


@pytest.fixture(autouse=True)
def restore_supplier_registry() -> None:
    _REGISTRY.clear()
    _register_default_suppliers()
    yield
    _REGISTRY.clear()
    _register_default_suppliers()


def test_supplier_runtime_config_defaults_to_fixture_mode() -> None:
    config = SupplierRuntimeConfig.default()

    assert config.use_fixture is True
    assert config.enable_live is False


def test_supplier_runtime_config_fixture_only() -> None:
    config = SupplierRuntimeConfig.fixture_only()

    assert config.use_fixture is True
    assert config.enable_live is False


def test_supplier_runtime_config_live_only() -> None:
    config = SupplierRuntimeConfig.live_only()

    assert config.use_fixture is False
    assert config.enable_live is True


def test_resolve_supplier_client_uses_default_fixture_behavior() -> None:
    client = resolve_supplier_client("fashionphile")

    assert client is not None
    assert client.supplier_name == "fashionphile"
