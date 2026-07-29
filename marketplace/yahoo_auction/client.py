"""Fixture-backed Yahoo Auction domestic market client."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from marketplace.yahoo_auction.exceptions import YahooAuctionDataError, YahooAuctionParseError
from marketplace.yahoo_auction.models import YahooAuctionListing

DEFAULT_FIXTURE_DIR = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "yahoo_auction"
)


class FakeYahooAuctionClient:
    """Search sold Yahoo Auction listings from local fixtures without network access."""

    def __init__(self, *, fixture_dir: Path | str | None = None) -> None:
        self._fixture_dir = Path(fixture_dir) if fixture_dir is not None else DEFAULT_FIXTURE_DIR

    def search_sold_items(
        self,
        keyword: str,
        *,
        page: int = 1,
        max_results: int = 20,
    ) -> list[YahooAuctionListing]:
        """Return sold listings filtered by keyword with pagination."""
        normalized_keyword = keyword.strip().lower()
        listings = self._load_all_listings()
        if normalized_keyword:
            listings = [
                listing
                for listing in listings
                if _matches_keyword(normalized_keyword, listing.title, listing.brand)
            ]

        start = max(page - 1, 0) * max_results
        end = start + max_results
        return listings[start:end]

    def _load_all_listings(self) -> list[YahooAuctionListing]:
        if not self._fixture_dir.exists():
            raise YahooAuctionDataError(f"Fixture directory not found: {self._fixture_dir}")

        listings: list[YahooAuctionListing] = []
        for fixture_path in sorted(self._fixture_dir.glob("*.json")):
            payload = json.loads(fixture_path.read_text(encoding="utf-8"))
            items = payload.get("listings", [])
            if not isinstance(items, list):
                raise YahooAuctionDataError(f"Invalid listings payload in {fixture_path.name}")
            for item in items:
                if isinstance(item, dict):
                    listings.append(_parse_listing(item))
        return listings


def _parse_listing(item: dict[str, Any]) -> YahooAuctionListing:
    try:
        listing_id = str(item["listing_id"])
        title = str(item["title"])
        price_jpy = int(item["price_jpy"])
    except (KeyError, TypeError, ValueError) as exc:
        raise YahooAuctionParseError("Sold listing is missing required fields") from exc

    metadata = item.get("metadata") or {}
    bid_count = item.get("bid_count")
    return YahooAuctionListing(
        listing_id=listing_id,
        title=title,
        brand=str(item["brand"]) if item.get("brand") else None,
        price_jpy=price_jpy,
        sold_date=str(item["sold_date"]) if item.get("sold_date") else None,
        bid_count=int(bid_count) if bid_count is not None else None,
        condition=str(item["condition"]) if item.get("condition") else None,
        url=str(item["url"]) if item.get("url") else None,
        metadata=dict(metadata) if isinstance(metadata, dict) else {},
    )


def _matches_keyword(query: str, *fields: str | None) -> bool:
    haystack = " ".join(field.lower() for field in fields if field)
    tokens = query.split()
    return all(token in haystack for token in tokens)
