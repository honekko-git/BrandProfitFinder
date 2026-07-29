"""Supplier source resolution for fixture and live client selection."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from supplier.base import SupplierClient
from supplier.config import SupplierRuntimeConfig

SupplierLiveFactory = Callable[[], SupplierClient]

_LIVE_REGISTRY: dict[str, SupplierLiveFactory] = {}


class SupplierSourceMode(StrEnum):
    """Resolved supplier data source mode."""

    FIXTURE = "FIXTURE"
    LIVE = "LIVE"


@dataclass(frozen=True, slots=True)
class SupplierResolution:
    """Result of resolving one supplier client."""

    supplier_name: str
    client: SupplierClient | None
    mode: SupplierSourceMode | None = None


class SupplierResolver:
    """Resolve supplier clients with explicit injection, fixture, then live priority."""

    def __init__(self, config: SupplierRuntimeConfig | None = None) -> None:
        self._config = config or SupplierRuntimeConfig.default()

    @property
    def config(self) -> SupplierRuntimeConfig:
        return self._config

    def resolve(
        self,
        supplier_name: str,
        *,
        injected_client: SupplierClient | None = None,
    ) -> SupplierResolution:
        """Resolve a supplier client using configured source priority."""
        normalized = _normalize_supplier_name(supplier_name)
        if not normalized:
            return SupplierResolution(supplier_name="", client=None, mode=None)

        if injected_client is not None:
            return SupplierResolution(
                supplier_name=normalized,
                client=injected_client,
                mode=None,
            )

        if self._config.use_fixture:
            fixture_client = _create_fixture_supplier_client(normalized)
            if fixture_client is not None:
                return SupplierResolution(
                    supplier_name=normalized,
                    client=fixture_client,
                    mode=SupplierSourceMode.FIXTURE,
                )

        if self._config.enable_live:
            live_client = _create_live_supplier_client(normalized)
            if live_client is not None:
                return SupplierResolution(
                    supplier_name=normalized,
                    client=live_client,
                    mode=SupplierSourceMode.LIVE,
                )

        return SupplierResolution(supplier_name=normalized, client=None, mode=None)


def register_live_supplier(name: str, factory: SupplierLiveFactory) -> None:
    """Register a live supplier client factory for future integrations."""
    normalized = _normalize_supplier_name(name)
    if not normalized:
        raise ValueError("supplier name must not be blank")
    _LIVE_REGISTRY[normalized] = factory


def _create_fixture_supplier_client(name: str) -> SupplierClient | None:
    from supplier.factory import create_supplier_client

    return create_supplier_client(name)


def _create_live_supplier_client(name: str) -> SupplierClient | None:
    factory = _LIVE_REGISTRY.get(name)
    if factory is None:
        return None
    return factory()


def _normalize_supplier_name(name: str) -> str:
    return name.strip().lower()
