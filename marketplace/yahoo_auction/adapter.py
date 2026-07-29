"""Domestic market price calculations from Yahoo Auction sold listings."""

from __future__ import annotations

from statistics import median

from marketplace.yahoo_auction.exceptions import YahooAuctionDataError
from marketplace.yahoo_auction.models import DomesticMarketPrice, YahooAuctionListing


def calculate_market_price(
    listings: list[YahooAuctionListing],
    *,
    product_keyword: str = "",
) -> DomesticMarketPrice:
    """
    Aggregate sold listings into a normalized domestic market price summary.

    Confidence score rules:
        sample_count >= 20 -> 1.0
        sample_count >= 10 -> 0.8
        sample_count >= 5  -> 0.6
        otherwise          -> 0.3
    """
    if not listings:
        raise YahooAuctionDataError("At least one sold listing is required")

    prices = [listing.price_jpy for listing in listings]
    sample_count = len(prices)
    average_price = sum(prices) / sample_count
    median_price = float(median(prices))

    return DomesticMarketPrice(
        product_keyword=product_keyword,
        average_price_jpy=average_price,
        median_price_jpy=median_price,
        min_price_jpy=min(prices),
        max_price_jpy=max(prices),
        sample_count=sample_count,
        confidence_score=_confidence_score(sample_count),
        metadata={
            "source": "yahoo_auction",
            "listing_ids": [listing.listing_id for listing in listings],
        },
    )


def _confidence_score(sample_count: int) -> float:
    if sample_count >= 20:
        return 1.0
    if sample_count >= 10:
        return 0.8
    if sample_count >= 5:
        return 0.6
    return 0.3
