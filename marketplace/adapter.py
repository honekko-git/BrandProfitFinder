"""
Standard marketplace adapter interface.

Extends BaseMarketplace with a stable adapter contract for identity-safe
marketplace integrations. Existing BaseMarketplace implementations remain
valid; new implementations should inherit MarketplaceAdapter.
"""

from __future__ import annotations

from marketplace.base_marketplace import BaseMarketplace
from marketplace_search.capability import MarketplaceCapability


class MarketplaceAdapter(BaseMarketplace):
    """
    Common adapter contract for marketplace search integrations.

    Subclasses implement the BaseMarketplace search/parse contract and may
    override capability metadata. Domain identity and comparison logic remain
    outside adapter implementations.
    """

    @property
    def adapter_id(self) -> str:
        """Return a stable adapter identifier (defaults to marketplace_name)."""
        return self.marketplace_name

    @property
    def adapter_version(self) -> str:
        """Return adapter schema/version label for diagnostics."""
        return "1.0"

    @property
    def uses_fixture_data(self) -> bool:
        """Return True when the adapter operates on synthetic fixture payloads only."""
        return False

    @property
    def supports_structured_identifiers(self) -> bool:
        """Return True when listings may include GTIN/model/style metadata."""
        return True

    @property
    def capability(self) -> MarketplaceCapability:
        """Return search capability metadata for this adapter."""
        return MarketplaceCapability.from_adapter(self)

    def adapter_metadata(self) -> dict[str, str]:
        """Return deterministic adapter capability metadata."""
        metadata = self.capability.as_dict()
        metadata["adapter_id"] = self.adapter_id
        metadata["marketplace_name"] = self.marketplace_name
        return metadata
