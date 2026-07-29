"""Fashionphile fixture/live client resolution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from supplier.base import SupplierClient
from supplier.fashionphile.client import FashionphileClient
from supplier.fashionphile.exceptions import FashionphileLiveUnavailableError
from supplier.fashionphile.live_client import FashionphileLiveClient
from supplier.fashionphile.settings import FashionphileSettings
from supplier.models import SupplierProduct, SupplierType


class FashionphileSourceMode(StrEnum):
    """Resolved Fashionphile supplier source mode."""

    LIVE = "LIVE"
    FIXTURE = "FIXTURE"


@dataclass(frozen=True, slots=True)
class FashionphileResolution:
    """Result of resolving a Fashionphile supplier client."""

    client: SupplierClient
    mode: FashionphileSourceMode


class FashionphileResolver:
    """Resolve Fashionphile clients across live and fixture sources."""

    def resolve(
        self,
        *,
        live_client: SupplierClient | None = None,
        settings: FashionphileSettings | None = None,
        fixture_client: SupplierClient | None = None,
    ) -> FashionphileResolution:
        """Resolve the Fashionphile client using live-first priority with fixture fallback."""
        runtime_settings = settings or FashionphileSettings.default()
        fixture = fixture_client or FashionphileClient()

        if live_client is not None:
            return FashionphileResolution(
                client=_FashionphileFallbackClient(live_client, fixture),
                mode=FashionphileSourceMode.LIVE,
            )

        if runtime_settings.live_enabled:
            live = FashionphileLiveClient(settings=runtime_settings)
            return FashionphileResolution(
                client=_FashionphileFallbackClient(live, fixture),
                mode=FashionphileSourceMode.LIVE,
            )

        return FashionphileResolution(client=fixture, mode=FashionphileSourceMode.FIXTURE)


class _FashionphileFallbackClient:
    """Route Fashionphile searches to live first, then fixture on live unavailability."""

    def __init__(self, primary: SupplierClient, fallback: SupplierClient) -> None:
        self._primary = primary
        self._fallback = fallback

    @property
    def supplier_name(self) -> str:
        return self._primary.supplier_name

    @property
    def supplier_type(self) -> SupplierType:
        return self._primary.supplier_type

    def search_products(
        self,
        query: str,
        *,
        page: int = 1,
        max_results: int = 20,
    ) -> list[SupplierProduct]:
        try:
            return self._primary.search_products(query, page=page, max_results=max_results)
        except FashionphileLiveUnavailableError:
            return self._fallback.search_products(query, page=page, max_results=max_results)
