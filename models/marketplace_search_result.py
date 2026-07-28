"""
Domestic marketplace search result model.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from models.marketplace_listing import MarketplaceListing
from models.product import Product

SEARCH_SUCCESS = "success"
SEARCH_NO_LISTINGS = "no_listings"
SEARCH_NO_VALID_LISTINGS = "no_valid_listings"
SEARCH_ERROR = "error"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class MarketplaceSearchResult:
    """Search outcome for one product on one domestic marketplace."""

    product: Product | None = None
    query: str = ""
    marketplace_name: str = ""
    listings: list[MarketplaceListing] = field(default_factory=list)
    valid_listings: list[MarketplaceListing] = field(default_factory=list)
    rejected_listings: list[MarketplaceListing] = field(default_factory=list)
    selected_listing: MarketplaceListing | None = None
    selected_price_jpy: Decimal | None = None
    selection_strategy: str = ""
    searched_at: datetime = field(default_factory=_utc_now)
    status: str = SEARCH_SUCCESS
    error_message: str = ""

    @property
    def has_valid_listings(self) -> bool:
        """Return True when at least one valid listing exists."""
        return bool(self.valid_listings)

    @property
    def listing_count(self) -> int:
        """Return total listing count."""
        return len(self.listings)
