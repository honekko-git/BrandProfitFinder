"""Tests for Mercari domestic market fixture client."""

from __future__ import annotations

from marketplace.domestic_market.clients.mercari import FakeMercariDomesticMarketClient


def test_mercari_client_loads_fixture_prices() -> None:
    client = FakeMercariDomesticMarketClient()

    prices = client.search_sold_items("chanel wallet", max_results=10)

    assert prices == [145000, 152000, 158000]


def test_mercari_client_filters_by_query() -> None:
    client = FakeMercariDomesticMarketClient()

    chanel_prices = client.search_sold_items("chanel wallet", max_results=10)
    lv_prices = client.search_sold_items("louis vuitton wallet", max_results=10)

    assert chanel_prices == [145000, 152000, 158000]
    assert lv_prices == [88000, 92000]


def test_mercari_client_returns_empty_for_unknown_query() -> None:
    client = FakeMercariDomesticMarketClient()

    prices = client.search_sold_items("unknown brand bag", max_results=10)

    assert prices == []


def test_mercari_client_supports_inline_empty_result() -> None:
    client = FakeMercariDomesticMarketClient([])

    assert client.search_sold_items("chanel wallet", max_results=10) == []
