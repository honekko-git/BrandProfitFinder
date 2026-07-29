"""HTTP transport placeholder for future live supplier integrations."""

from __future__ import annotations

from typing import Any

from supplier.live.models import SupplierLiveResponse


class SupplierHttpTransport:
    """HTTP execution entry point for live supplier clients."""

    def get(self, url: str, **kwargs: Any) -> SupplierLiveResponse:
        """Execute an HTTP GET request against a live supplier endpoint."""
        raise NotImplementedError("Live supplier HTTP transport is not implemented")

    def post(self, url: str, **kwargs: Any) -> SupplierLiveResponse:
        """Execute an HTTP POST request against a live supplier endpoint."""
        raise NotImplementedError("Live supplier HTTP transport is not implemented")
