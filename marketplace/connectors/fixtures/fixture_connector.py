"""Fixture-backed market connector implementations."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from marketplace.connectors.models import MarketListing

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"

SUPPORTED_MARKETS: tuple[str, ...] = (
    "Fashionphile",
    "The RealReal",
    "Vestiaire Collective",
    "Mercari",
    "Yahoo Auction",
)

MARKET_FIXTURE_FILES: dict[str, str] = {
    "Fashionphile": "fashionphile_search_page_1.json",
    "The RealReal": "therealreal_search_page_1.json",
    "Vestiaire Collective": "vestiaire_search_page_1.json",
    "Mercari": "domestic_market/mercari_chanel_wallet.json",
    "Yahoo Auction": "yahoo_auction/chanel_wallet.json",
}


class FixtureMarketConnector:
    """Load local fixture JSON and expose normalized MarketListing rows."""

    def __init__(
        self,
        market_name: str,
        *,
        fixtures_dir: Path | None = None,
        listings: list[MarketListing] | None = None,
    ) -> None:
        normalized = market_name.strip()
        if normalized not in SUPPORTED_MARKETS:
            raise ValueError(f"Unsupported fixture market: {market_name}")
        self._market_name = normalized
        self._fixtures_dir = fixtures_dir or FIXTURES_DIR
        self._listings = listings if listings is not None else self._load_listings()

    @property
    def market_name(self) -> str:
        return self._market_name

    @property
    def source_type(self) -> str:
        return "FIXTURE"

    def search_products(self, query: str) -> list[MarketListing]:
        normalized_query = query.strip().lower()
        if not normalized_query:
            return list(self._listings)
        return [
            listing
            for listing in self._listings
            if normalized_query in listing.title.lower()
            or normalized_query in listing.brand.lower()
            or normalized_query in listing.category.lower()
        ]

    def get_product(self, url: str) -> MarketListing | None:
        normalized = url.strip()
        for listing in self._listings:
            if listing.url == normalized:
                return listing
        return None

    def _load_listings(self) -> list[MarketListing]:
        fixture_name = MARKET_FIXTURE_FILES[self._market_name]
        fixture_path = self._fixtures_dir / fixture_name
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        if self._market_name == "Mercari":
            return _parse_mercari_fixture(payload, market_name=self._market_name)
        if self._market_name == "Yahoo Auction":
            return _parse_yahoo_auction_fixture(payload, market_name=self._market_name)
        return _parse_items_fixture(payload, market_name=self._market_name)


def _parse_items_fixture(payload: dict, *, market_name: str) -> list[MarketListing]:
    created_at = datetime.now(tz=UTC)
    listings: list[MarketListing] = []
    for item in payload.get("items", []):
        price_payload = item.get("price", {})
        amount = price_payload.get("amount", 0)
        currency = str(price_payload.get("currency", "JPY"))
        condition = _extract_condition(item)
        listings.append(
            MarketListing(
                id=str(item.get("listing_id", "")),
                title=str(item.get("title", "")),
                brand=str(item.get("brand", "")),
                category=str(item.get("category", "bag")),
                condition=condition,
                price=Decimal(str(amount)),
                currency=currency,
                market_name=market_name,
                url=str(item.get("url", "")),
                source_type="FIXTURE",
                created_at=created_at,
            )
        )
    return listings


def _parse_yahoo_auction_fixture(payload: dict, *, market_name: str) -> list[MarketListing]:
    created_at = datetime.now(tz=UTC)
    listings: list[MarketListing] = []
    for item in payload.get("listings", []):
        listings.append(
            MarketListing(
                id=str(item.get("listing_id", "")),
                title=str(item.get("title", "")),
                brand=str(item.get("brand", "")),
                category="wallet",
                condition=str(item.get("condition", "used")),
                price=Decimal(str(item.get("price_jpy", 0))),
                currency="JPY",
                market_name=market_name,
                url=str(item.get("url", "")),
                source_type="FIXTURE",
                created_at=created_at,
            )
        )
    return listings


def _parse_mercari_fixture(payload: dict, *, market_name: str) -> list[MarketListing]:
    created_at = datetime.now(tz=UTC)
    keyword = str(payload.get("product_keyword", "mercari item"))
    brand = keyword.split()[0].title() if keyword else "Unknown"
    listings: list[MarketListing] = []
    for index, price in enumerate(payload.get("sold_prices", []), start=1):
        listings.append(
            MarketListing(
                id=f"mercari-{index}",
                title=f"{keyword.title()} #{index}",
                brand=brand,
                category="wallet",
                condition="used",
                price=Decimal(str(price)),
                currency="JPY",
                market_name=market_name,
                url=f"https://jp.mercari.com/item/mercari-{index}",
                source_type="FIXTURE",
                created_at=created_at,
            )
        )
    return listings


def _extract_condition(item: dict) -> str:
    raw_condition = item.get("condition")
    if isinstance(raw_condition, dict):
        return str(raw_condition.get("raw", "used"))
    if isinstance(raw_condition, str) and raw_condition.strip():
        return raw_condition
    return "used"
