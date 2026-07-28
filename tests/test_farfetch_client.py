"""Tests for Farfetch fake client."""

import json
from pathlib import Path

import pytest

from marketplace.farfetch_client import FakeFarfetchClient

FIXTURES = Path(__file__).parent / "fixtures"


def test_fixture_return() -> None:
    payload = json.loads((FIXTURES / "farfetch_search_normal.json").read_text(encoding="utf-8"))
    client = FakeFarfetchClient(payload)
    assert client.search_items("gucci")["total"] == 3


def test_records_query_page_filters() -> None:
    client = FakeFarfetchClient({"items": [], "total": 0})
    client.search_items("marmont", page=2, page_size=10, filters={"brand": "GUCCI"})
    assert client.last_query == "marmont"
    assert client.last_page == 2
    assert client.last_page_size == 10
    assert client.last_filters == {"brand": "GUCCI"}


def test_call_count() -> None:
    client = FakeFarfetchClient({"items": [], "total": 0})
    client.search_items("a")
    client.search_items("b")
    assert client.call_count == 2


def test_injected_exception() -> None:
    client = FakeFarfetchClient(error=RuntimeError("fail"))
    with pytest.raises(RuntimeError):
        client.search_items("x")


def test_multi_page() -> None:
    p1 = json.loads((FIXTURES / "farfetch_search_page_1.json").read_text(encoding="utf-8"))
    p2 = json.loads((FIXTURES / "farfetch_search_page_2.json").read_text(encoding="utf-8"))
    client = FakeFarfetchClient(pages={1: p1, 2: p2})
    assert client.search_items("gucci", page=2)["page"] == 2


def test_defensive_copy() -> None:
    payload = {"items": [], "total": 0, "page": 1}
    client = FakeFarfetchClient(payload)
    result = client.search_items("x")
    result["total"] = 99
    assert client.search_items("x")["total"] == 0
