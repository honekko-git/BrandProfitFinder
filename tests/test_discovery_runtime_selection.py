"""Tests for discovery runtime supplier selection preparation."""

from __future__ import annotations

from unittest.mock import patch

from profit_discovery.cli.discovery_command import build_default_discovery_runner, build_default_supplier_client
from supplier.adapters.source_resolver import SupplierSourceMode, SupplierResolver
from supplier.config import SupplierRuntimeConfig
from supplier.fashionphile.client import FashionphileClient


def test_build_default_supplier_client_uses_resolver() -> None:
    with patch("profit_discovery.cli.discovery_command.resolve_supplier_client") as resolve_mock:
        resolve_mock.return_value = FashionphileClient()

        client = build_default_supplier_client()

    resolve_mock.assert_called_once_with(
        "fashionphile",
        config=SupplierRuntimeConfig.default(),
    )
    assert client is not None
    assert client.supplier_name == "fashionphile"


def test_build_default_discovery_runner_uses_resolved_supplier_client() -> None:
    with patch(
        "profit_discovery.cli.discovery_command.build_default_supplier_client",
        return_value=FashionphileClient(),
    ) as supplier_mock:
        runner = build_default_discovery_runner()

    supplier_mock.assert_called_once_with("fashionphile", config=SupplierRuntimeConfig.default())
    assert runner.discovery_runner.supplier_client.supplier_name == "fashionphile"


def test_resolver_fixture_mode_matches_discovery_default_supplier() -> None:
    resolution = SupplierResolver(SupplierRuntimeConfig.default()).resolve("fashionphile")

    assert resolution.client is not None
    assert resolution.mode is SupplierSourceMode.FIXTURE
    assert resolution.client.supplier_name == "fashionphile"
