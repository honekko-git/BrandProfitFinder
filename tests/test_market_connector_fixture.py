"""Tests for fixture market connector."""

from __future__ import annotations

from marketplace.connectors.fixtures import FixtureMarketConnector


def test_fixture_connector_returns_market_listings_for_fashionphile() -> None:
    connector = FixtureMarketConnector("Fashionphile")
    listings = connector.search_products("GUCCI")

    assert listings
    assert listings[0].market_name == "Fashionphile"
    assert listings[0].source_type == "FIXTURE"
    assert listings[0].currency == "JPY"
    assert listings[0].url.startswith("https://")


def test_fixture_connector_returns_yahoo_auction_listings() -> None:
    connector = FixtureMarketConnector("Yahoo Auction")
    listings = connector.search_products("Chanel")

    assert listings
    assert listings[0].market_name == "Yahoo Auction"
    assert listings[0].brand == "Chanel"


def test_fixture_connector_get_product_by_url() -> None:
    connector = FixtureMarketConnector("Yahoo Auction")
    listings = connector.search_products("Chanel")
    listing = connector.get_product(listings[0].url)

    assert listing is not None
    assert listing.id == listings[0].id


def test_fixture_connector_returns_mercari_listings() -> None:
    connector = FixtureMarketConnector("Mercari")
    listings = connector.search_products("chanel")

    assert listings
    assert listings[0].market_name == "Mercari"
    assert listings[0].condition == "used"
