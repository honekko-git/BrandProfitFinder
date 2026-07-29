"""Tests for Yahoo Auction domestic market price adapter."""

from __future__ import annotations

import pytest

from marketplace.yahoo_auction.adapter import calculate_market_price
from marketplace.yahoo_auction.exceptions import YahooAuctionDataError
from marketplace.yahoo_auction.models import YahooAuctionListing


def _listings(prices: list[int]) -> list[YahooAuctionListing]:
    return [
        YahooAuctionListing(
            listing_id=f"ya-test-{index}",
            title=f"Test Listing {index}",
            brand="Test Brand",
            price_jpy=price,
        )
        for index, price in enumerate(prices, start=1)
    ]


def test_calculate_market_price_average_and_median() -> None:
    market_price = calculate_market_price(
        _listings([155000, 160000, 165000, 158000, 162000]),
        product_keyword="chanel wallet",
    )

    assert market_price.average_price_jpy == 160000.0
    assert market_price.median_price_jpy == 160000.0
    assert market_price.min_price_jpy == 155000
    assert market_price.max_price_jpy == 165000


def test_calculate_market_price_confidence_score_thresholds() -> None:
    five_samples = calculate_market_price(_listings([100000] * 5))
    ten_samples = calculate_market_price(_listings([100000] * 10))
    twenty_samples = calculate_market_price(_listings([100000] * 20))

    assert five_samples.confidence_score == 0.6
    assert ten_samples.confidence_score == 0.8
    assert twenty_samples.confidence_score == 1.0


def test_calculate_market_price_requires_listings() -> None:
    with pytest.raises(YahooAuctionDataError):
        calculate_market_price([])
