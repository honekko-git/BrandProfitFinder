"""Parser for Yahoo Auction live/API responses."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from marketplace.connectors.live.exceptions import MarketConnectorParseError
from marketplace.connectors.models import MarketListing


def parse_yahoo_auction_response(payload: dict) -> list[MarketListing]:
    """Convert one Yahoo Auction JSON payload into MarketListing rows."""
    listings_data = payload.get("listings")
    if not isinstance(listings_data, list):
        raise MarketConnectorParseError("Yahoo Auction response missing listings array")

    created_at = datetime.now(tz=UTC)
    listings: list[MarketListing] = []
    for item in listings_data:
        if not isinstance(item, dict):
            continue
        price_jpy = item.get("price_jpy", item.get("price", 0))
        listings.append(
            MarketListing(
                id=str(item.get("listing_id", "")),
                title=str(item.get("title", "")),
                brand=str(item.get("brand", "")),
                category=str(item.get("category", "wallet")),
                condition=str(item.get("condition", "used")),
                price=Decimal(str(price_jpy)),
                currency="JPY",
                market_name="Yahoo Auction",
                url=str(item.get("url", "")),
                source_type="LIVE",
                created_at=created_at,
            )
        )
    return listings
