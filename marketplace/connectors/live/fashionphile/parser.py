"""Parser for Fashionphile live/API responses."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from marketplace.connectors.live.exceptions import MarketConnectorParseError
from marketplace.connectors.models import MarketListing


def parse_fashionphile_response(payload: dict) -> list[MarketListing]:
    """Convert one Fashionphile JSON payload into MarketListing rows."""
    items = _extract_items(payload)
    if not items:
        raise MarketConnectorParseError("Fashionphile response missing listing rows")

    created_at = datetime.now(tz=UTC)
    listings: list[MarketListing] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        amount, currency = _extract_price(item)
        condition = _extract_condition(item)
        listing_id = str(item.get("listing_id") or item.get("external_id") or "")
        listings.append(
            MarketListing(
                id=listing_id,
                title=str(item.get("title", "")),
                brand=str(item.get("brand", "")),
                category=str(item.get("category", "bag")),
                condition=condition,
                price=Decimal(str(amount)),
                currency=currency,
                market_name="Fashionphile",
                url=str(item.get("url", "")),
                source_type="LIVE",
                created_at=created_at,
            )
        )
    return listings


def _extract_items(payload: dict) -> list[dict]:
    for key in ("items", "products"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def _extract_price(item: dict) -> tuple[object, str]:
    price_payload = item.get("price", {})
    if isinstance(price_payload, dict):
        amount = price_payload.get("amount", 0)
        currency = str(price_payload.get("currency", "JPY"))
        return amount, currency
    if item.get("price") is not None:
        return item.get("price", 0), str(item.get("currency", "USD"))
    return 0, "JPY"


def _extract_condition(item: dict) -> str:
    raw_condition = item.get("condition")
    if isinstance(raw_condition, dict):
        return str(raw_condition.get("raw", "used"))
    if isinstance(raw_condition, str) and raw_condition.strip():
        return raw_condition
    return "used"
