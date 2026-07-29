"""Tests for Yahoo Auction fixture client."""

from __future__ import annotations

from marketplace.yahoo_auction.base import YahooAuctionClientProtocol
from marketplace.yahoo_auction.client import FakeYahooAuctionClient


def test_fake_yahoo_auction_client_loads_fixtures() -> None:
    client = FakeYahooAuctionClient()

    listings = client.search_sold_items("chanel wallet", max_results=10)

    assert len(listings) == 5
    assert all(listing.price_jpy > 0 for listing in listings)


def test_fake_yahoo_auction_client_filters_by_brand() -> None:
    client = FakeYahooAuctionClient()

    gucci_results = client.search_sold_items("Gucci")
    lv_results = client.search_sold_items("Louis Vuitton")

    assert len(gucci_results) == 3
    assert gucci_results[0].brand == "Gucci"
    assert len(lv_results) == 3
    assert lv_results[0].brand == "Louis Vuitton"


def test_fake_yahoo_auction_client_supports_pagination() -> None:
    client = FakeYahooAuctionClient()

    first_page = client.search_sold_items("chanel", page=1, max_results=2)
    second_page = client.search_sold_items("chanel", page=2, max_results=2)

    assert len(first_page) == 2
    assert len(second_page) == 2
    assert first_page[0].listing_id != second_page[0].listing_id


def test_fake_yahoo_auction_client_matches_protocol() -> None:
    client = FakeYahooAuctionClient()

    assert isinstance(client, YahooAuctionClientProtocol)
