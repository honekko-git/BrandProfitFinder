"""Live Fashionphile supplier client foundation."""

from __future__ import annotations

from urllib.parse import urlencode

from supplier.fashionphile.adapter import live_response_to_supplier_products
from supplier.fashionphile.exceptions import FashionphileConfigError, FashionphileLiveUnavailableError
from supplier.fashionphile.settings import FashionphileSettings
from supplier.live.transport import SupplierHttpTransport
from supplier.models import SupplierProduct, SupplierType


class FashionphileLiveClient:
    """Live Fashionphile supplier client using the shared HTTP transport entry point."""

    def __init__(
        self,
        *,
        settings: FashionphileSettings | None = None,
        transport: SupplierHttpTransport | None = None,
    ) -> None:
        self._settings = settings or FashionphileSettings.default()
        self._transport = transport or SupplierHttpTransport()

    @property
    def supplier_name(self) -> str:
        return "fashionphile"

    @property
    def supplier_type(self) -> SupplierType:
        return SupplierType.USED

    def search_products(
        self,
        query: str,
        *,
        page: int = 1,
        max_results: int = 20,
    ) -> list[SupplierProduct]:
        """Search Fashionphile live inventory through the transport layer."""
        if not self._settings.live_enabled:
            raise FashionphileLiveUnavailableError("Fashionphile live search is disabled")

        if not self._settings.endpoint:
            raise FashionphileConfigError("Fashionphile live endpoint is not configured")

        params = urlencode(
            {
                "query": query.strip(),
                "page": page,
                "max_results": max_results,
            }
        )
        url = f"{self._settings.endpoint.rstrip('/')}/search?{params}"
        headers = {}
        if self._settings.api_key:
            headers["Authorization"] = f"Bearer {self._settings.api_key}"

        try:
            response = self._transport.get(url, headers=headers)
        except NotImplementedError as exc:
            raise FashionphileLiveUnavailableError(
                "Fashionphile live transport is not implemented"
            ) from exc

        return live_response_to_supplier_products(response)
