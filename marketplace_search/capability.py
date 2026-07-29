"""Marketplace search capability descriptors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class MarketplaceCapability:
    """Describe marketplace search features for routing and validation."""

    marketplace_id: str
    adapter_version: str = "1.0"
    supports_text_search: bool = True
    supports_sku_search: bool = True
    supports_model_search: bool = True
    supports_jan_search: bool = False
    supports_pagination: bool = True
    supports_structured_identifiers: bool = True
    uses_fixture_data: bool = False
    requires_configured_client: bool = False
    max_page_size: int = 100

    @classmethod
    def from_adapter(cls, adapter: Any) -> MarketplaceCapability:
        """Build capability metadata from a marketplace adapter."""
        marketplace_id = getattr(adapter, "adapter_id", None) or getattr(adapter, "marketplace_name", "")
        supports_jan = marketplace_id in {
            "stockx",
            "goat",
            "rakuten",
            "yahoo",
            "yahoo_auction",
            "amazon_jp",
        }
        uses_fixture = bool(getattr(adapter, "uses_fixture_data", False))
        return cls(
            marketplace_id=marketplace_id,
            adapter_version=getattr(adapter, "adapter_version", "1.0"),
            supports_text_search=True,
            supports_sku_search=True,
            supports_model_search=True,
            supports_jan_search=supports_jan,
            supports_pagination=True,
            supports_structured_identifiers=bool(getattr(adapter, "supports_structured_identifiers", True)),
            uses_fixture_data=uses_fixture,
            requires_configured_client=uses_fixture,
            max_page_size=100,
        )

    def as_dict(self) -> dict[str, str]:
        """Return deterministic capability metadata for diagnostics."""
        return {
            "marketplace_id": self.marketplace_id,
            "adapter_version": self.adapter_version,
            "supports_text_search": str(self.supports_text_search),
            "supports_sku_search": str(self.supports_sku_search),
            "supports_model_search": str(self.supports_model_search),
            "supports_jan_search": str(self.supports_jan_search),
            "supports_pagination": str(self.supports_pagination),
            "supports_structured_identifiers": str(self.supports_structured_identifiers),
            "uses_fixture_data": str(self.uses_fixture_data),
            "requires_configured_client": str(self.requires_configured_client),
            "max_page_size": str(self.max_page_size),
        }
