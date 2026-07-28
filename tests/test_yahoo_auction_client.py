"""Unit tests for marketplace.yahoo_auction_client."""

import json
from pathlib import Path

import pytest

from marketplace.yahoo_auction_client import FakeYahooAuctionClient

FIXTURES = Path(__file__).parent / "fixtures"


def test_fake_client_returns_fixture() -> None:
    payload = json.loads((FIXTURES / "yahoo_auction_search_normal.json").read_text(encoding="utf-8"))
    client = FakeYahooAuctionClient(payload)
    result = client.search_items(query="gucci wallet")
    assert result["total_results"] == 1
    assert len(result["items"]) == 1


def test_fake_client_records_query() -> None:
    client = FakeYahooAuctionClient({"items": []})
    client.search_items(query="gucci bag")
    assert client.last_query == "gucci bag"


def test_fake_client_records_page() -> None:
    client = FakeYahooAuctionClient({"items": []})
    client.search_items(query="bag", page=3)
    assert client.last_page == 3


def test_fake_client_records_hits() -> None:
    client = FakeYahooAuctionClient({"items": []})
    client.search_items(query="bag", hits=10)
    assert client.last_hits == 10


def test_fake_client_records_sort() -> None:
    client = FakeYahooAuctionClient({"items": []})
    client.search_items(query="bag", sort="end_time")
    assert client.last_sort == "end_time"


def test_fake_client_injected_exception() -> None:
    client = FakeYahooAuctionClient(error=RuntimeError("injected failure"))
    with pytest.raises(RuntimeError, match="injected failure"):
        client.search_items(query="bag")


def test_fake_client_no_network() -> None:
    client = FakeYahooAuctionClient({"items": [], "total_results": 0})
    result = client.search_items(query="test")
    assert result == {"items": [], "total_results": 0}
