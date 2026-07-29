"""Tests for Yahoo Auction domestic market models."""

from __future__ import annotations

from marketplace.yahoo_auction.models import DomesticMarketPrice, YahooAuctionListing


def test_yahoo_auction_listing_creation() -> None:
    listing = YahooAuctionListing(
        listing_id="ya-chanel-001",
        title="Chanel Classic Wallet Black Caviar",
        brand="Chanel",
        price_jpy=160000,
        sold_date="2026-07-01",
        bid_count=18,
        condition="used",
        url="https://example.invalid/yahoo-auction/ya-chanel-001",
        metadata={"source": "fixture"},
    )

    assert listing.listing_id == "ya-chanel-001"
    assert listing.price_jpy == 160000
    assert listing.brand == "Chanel"


def test_domestic_market_price_creation() -> None:
    market_price = DomesticMarketPrice(
        product_keyword="chanel wallet",
        average_price_jpy=160000.0,
        median_price_jpy=160000.0,
        min_price_jpy=155000,
        max_price_jpy=165000,
        sample_count=5,
        confidence_score=0.6,
        metadata={"source": "yahoo_auction"},
    )

    assert market_price.product_keyword == "chanel wallet"
    assert market_price.sample_count == 5
    assert market_price.confidence_score == 0.6
