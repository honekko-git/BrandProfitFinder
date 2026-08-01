"""Normalize Yahoo sold/listing payloads without assuming one vendor format."""

from __future__ import annotations

from statistics import median


def extract_yahoo_items(payload: object) -> list[dict]:
    """Extract listing rows from common Yahoo JSON payload shapes."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("items", "listings"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [item for item in rows if isinstance(item, dict)]
    return []


def normalize_yahoo_sold_item(item: dict) -> dict[str, object] | None:
    """Normalize one Yahoo listing row into sold-price transport fields."""
    title = item.get("title")
    sold_price = (
        item.get("sold_price")
        if item.get("sold_price") is not None
        else item.get("price_jpy")
        if item.get("price_jpy") is not None
        else item.get("price")
        if item.get("price") is not None
        else item.get("winning_price")
        if item.get("winning_price") is not None
        else item.get("current_price")
    )
    if not title or sold_price is None:
        return None
    try:
        price = int(sold_price)
    except (TypeError, ValueError):
        return None
    if price <= 0:
        return None

    normalized: dict[str, object] = {
        "title": str(title).strip(),
        "sold_price": price,
    }
    if item.get("url") is not None:
        normalized["url"] = str(item["url"])
    if item.get("sold_date") is not None:
        normalized["sold_date"] = str(item["sold_date"])
    return normalized


def normalize_yahoo_sold_payload(payload: object) -> list[dict[str, object]]:
    """Convert one Yahoo JSON payload into normalized sold listing rows."""
    normalized: list[dict[str, object]] = []
    for item in extract_yahoo_items(payload):
        row = normalize_yahoo_sold_item(item)
        if row is not None:
            normalized.append(row)
    return normalized


def summarize_sold_prices(items: list[dict[str, object]]) -> dict[str, object]:
    """Summarize sold prices for profit validation display."""
    prices = [int(item["sold_price"]) for item in items if item.get("sold_price") is not None]
    if not prices:
        return {
            "sample_count": 0,
            "average_price_jpy": 0.0,
            "median_price_jpy": 0.0,
            "listing_url": "",
        }
    listing_url = str(items[0].get("url", "")) if items[0].get("url") else ""
    return {
        "sample_count": len(prices),
        "average_price_jpy": sum(prices) / len(prices),
        "median_price_jpy": float(median(prices)),
        "listing_url": listing_url,
    }
