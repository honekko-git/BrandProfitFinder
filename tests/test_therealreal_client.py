"""Tests for The RealReal fake client."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from marketplace.therealreal_client import FakeTheRealRealClient

FIXTURES = Path(__file__).parent / "fixtures"


def test_fixture_return() -> None:
    payload = json.loads((FIXTURES / "therealreal_search_normal.json").read_text(encoding="utf-8"))
    client = FakeTheRealRealClient(payload)
    assert client.search_items("lv")["total"] == 1


def test_records_query_page_filters() -> None:
    client = FakeTheRealRealClient({"items": [], "total": 0})
    client.search_items("bag", page=2, page_size=10, filters={"brand": "LV"})
    assert client.last_query == "bag"
    assert client.last_page == 2
    assert client.last_filters == {"brand": "LV"}


def test_call_count() -> None:
    client = FakeTheRealRealClient({"items": [], "total": 0})
    client.search_items("a")
    client.search_items("b")
    assert client.call_count == 2


def test_injected_exception() -> None:
    client = FakeTheRealRealClient(error=RuntimeError("fail"))
    with pytest.raises(RuntimeError):
        client.search_items("x")


def test_multi_page() -> None:
    p1 = json.loads((FIXTURES / "therealreal_search_page_1.json").read_text(encoding="utf-8"))
    p2 = json.loads((FIXTURES / "therealreal_search_page_2.json").read_text(encoding="utf-8"))
    client = FakeTheRealRealClient(pages={1: p1, 2: p2})
    assert client.search_items("gucci", page=2)["page"] == 2


def test_defensive_copy() -> None:
    payload = {"items": [], "total": 0, "page": 1}
    client = FakeTheRealRealClient(payload)
    result = client.search_items("x")
    result["total"] = 99
    assert client.search_items("x")["total"] == 0


def test_filters_defensive_copy() -> None:
    client = FakeTheRealRealClient({"items": [], "total": 0})
    filters = {"brand": "LV"}
    client.search_items("x", filters=filters)
    filters["brand"] = "CHANGED"
    assert client.last_filters == {"brand": "LV"}
