"""Converters between imported listings and storage records."""

from __future__ import annotations

from datetime import UTC, datetime

from app.storage.market_listing_models import MarketListingRecord
from marketplace.connectors.models import MarketListing
from marketplace.importers.converters import market_listing_to_record_fields


def market_listing_record_from_listing(listing: MarketListing) -> MarketListingRecord:
    """Convert one MarketListing into a storage record."""
    fields = market_listing_to_record_fields(listing)
    created_at = listing.created_at if listing.created_at.tzinfo else listing.created_at.replace(tzinfo=UTC)
    return MarketListingRecord(
        id=None,
        title=str(fields["title"]),
        brand=str(fields["brand"]),
        category=str(fields["category"]),
        condition=str(fields["condition"]),
        price=float(fields["price"]),
        currency=str(fields["currency"]),
        market_name=str(fields["market_name"]),
        url=str(fields["url"]),
        external_key=str(fields["external_key"]),
        created_at=created_at,
    )
