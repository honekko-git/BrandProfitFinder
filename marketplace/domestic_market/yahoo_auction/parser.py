"""Parse Yahoo Auction live payloads into domestic market price data."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from marketplace.domestic_market.yahoo_auction.exceptions import YahooAuctionLiveUnavailableError


@dataclass(frozen=True, slots=True)
class ParsedSoldItem:
    """One parsed sold listing from a Yahoo Auction transport payload."""

    title: str
    sold_price: int
    url: str | None = None
    sold_date: str | None = None


def parse_sold_items(items: list[dict[str, object]]) -> list[ParsedSoldItem]:
    """Parse raw transport payloads into normalized sold listing records."""
    parsed: list[ParsedSoldItem] = []
    for item in items:
        try:
            title = str(item["title"]).strip()
            sold_price = int(item["sold_price"])
        except (KeyError, TypeError, ValueError) as exc:
            raise YahooAuctionLiveUnavailableError(
                "Yahoo Auction live payload is missing required sold listing fields"
            ) from exc
        if not title or sold_price <= 0:
            continue
        parsed.append(
            ParsedSoldItem(
                title=title,
                sold_price=sold_price,
                url=str(item["url"]) if item.get("url") else None,
                sold_date=str(item["sold_date"]) if item.get("sold_date") else None,
            )
        )
    return parsed


def calculate_average_price(items: list[ParsedSoldItem]) -> float:
    """Calculate the average sold price from parsed listings."""
    if not items:
        return 0.0
    return sum(item.sold_price for item in items) / len(items)


def to_market_price_data(
    items: list[ParsedSoldItem],
    *,
    product_keyword: str = "",
) -> dict[str, object]:
    """Build DomesticMarketPrice-compatible summary data from parsed listings."""
    if not items:
        return {
            "product_keyword": product_keyword,
            "average_price_jpy": 0.0,
            "median_price_jpy": 0.0,
            "min_price_jpy": 0,
            "max_price_jpy": 0,
            "sample_count": 0,
            "confidence_score": 0.0,
        }

    prices = [item.sold_price for item in items]
    sample_count = len(prices)
    return {
        "product_keyword": product_keyword,
        "average_price_jpy": calculate_average_price(items),
        "median_price_jpy": float(median(prices)),
        "min_price_jpy": min(prices),
        "max_price_jpy": max(prices),
        "sample_count": sample_count,
        "confidence_score": _confidence_score(sample_count),
    }


def _confidence_score(sample_count: int) -> float:
    if sample_count >= 20:
        return 1.0
    if sample_count >= 10:
        return 0.8
    if sample_count >= 5:
        return 0.6
    return 0.3
