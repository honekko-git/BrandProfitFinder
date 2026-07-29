"""Live supplier client resolution."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from supplier.base import SupplierClient
from supplier.live.base import SupplierLiveClient

SupplierLiveFactory = Callable[[], SupplierLiveClient | SupplierClient]

_LIVE_REGISTRY: dict[str, SupplierLiveFactory] = {}


class LiveSupplierSourceMode(StrEnum):
    """Resolved live supplier data source mode."""

    LIVE = "LIVE"
    FIXTURE = "FIXTURE"


@dataclass(frozen=True, slots=True)
class LiveSupplierResolution:
    """Result of resolving one live supplier client."""

    supplier_name: str
    client: SupplierClient | None
    mode: LiveSupplierSourceMode | None = None


class LiveSupplierResolver:
    """Resolve supplier clients with explicit, live, then fixture priority."""

    def resolve(
        self,
        supplier_name: str,
        *,
        injected_client: SupplierClient | None = None,
    ) -> LiveSupplierResolution:
        """Resolve a supplier client for live runtime selection."""
        normalized = _normalize_supplier_name(supplier_name)
        if not normalized:
            return LiveSupplierResolution(supplier_name="", client=None, mode=None)

        if injected_client is not None:
            return LiveSupplierResolution(
                supplier_name=normalized,
                client=injected_client,
                mode=None,
            )

        live_client = _create_live_client(normalized)
        if live_client is not None:
            return LiveSupplierResolution(
                supplier_name=normalized,
                client=live_client,
                mode=LiveSupplierSourceMode.LIVE,
            )

        fixture_client = _create_fixture_client(normalized)
        if fixture_client is not None:
            return LiveSupplierResolution(
                supplier_name=normalized,
                client=fixture_client,
                mode=LiveSupplierSourceMode.FIXTURE,
            )

        return LiveSupplierResolution(supplier_name=normalized, client=None, mode=None)


def register_live_supplier_client(name: str, factory: SupplierLiveFactory) -> None:
    """Register a live supplier client factory."""
    normalized = _normalize_supplier_name(name)
    if not normalized:
        raise ValueError("supplier name must not be blank")
    _LIVE_REGISTRY[normalized] = factory


def _create_live_client(name: str) -> SupplierClient | None:
    factory = _LIVE_REGISTRY.get(name)
    if factory is None:
        return None
    return factory()


def _create_fixture_client(name: str) -> SupplierClient | None:
    from supplier.factory import create_supplier_client

    return create_supplier_client(name)


def _normalize_supplier_name(name: str) -> str:
    return name.strip().lower()
