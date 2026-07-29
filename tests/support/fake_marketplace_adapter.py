"""Fake marketplace adapter for transport integration validation.

Mirrors the future Version 2 pattern where a marketplace adapter delegates
HTTP I/O to ``HttpTransport`` without importing production marketplace code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from utils.transport import HttpTransport, TransportRequestMetadata, TransportResponse


@dataclass
class FakeMarketplaceAdapter:
    """
    Stand-in marketplace adapter that routes search calls through HttpTransport.

    Used only in tests to validate transport integration boundaries before
    real marketplace clients are migrated.
    """

    marketplace_name: str
    transport: HttpTransport
    base_url: str = "https://api.fake-market.example/v1"
    default_headers: Mapping[str, str] = field(default_factory=dict)

    @property
    def adapter_id(self) -> str:
        """Return stable adapter identifier."""
        return self.marketplace_name

    def search_listings(self, query: str) -> dict[str, Any]:
        """
        Search listings via GET and return parsed JSON payload.

        Raises transport exceptions on failure.
        """
        response = self.fetch_listings(query)
        return response.json()

    def fetch_listings(self, query: str) -> TransportResponse:
        """Execute listing search and return the raw transport response."""
        metadata = TransportRequestMetadata(
            marketplace_name=self.marketplace_name,
            operation="search_listings",
            request_id=f"{self.marketplace_name}:search",
            tags=("integration", "listings"),
        )
        headers = dict(self.default_headers)
        return self.transport.get(
            f"{self.base_url}/listings",
            params={"q": query},
            headers=headers,
            metadata=metadata,
        )

    def create_watchlist_entry(self, listing_id: str) -> TransportResponse:
        """Execute listing mutation via POST."""
        metadata = TransportRequestMetadata(
            marketplace_name=self.marketplace_name,
            operation="create_watchlist_entry",
        )
        return self.transport.post(
            f"{self.base_url}/watchlist",
            json={"listing_id": listing_id},
            metadata=metadata,
        )
