"""Tests for Chrono24 fake client."""

import json
from pathlib import Path

import pytest

from marketplace.chrono24_client import FakeChrono24Client

FIXTURES = Path(__file__).parent / "fixtures"


def test_fixture_return() -> None:
    payload = json.loads((FIXTURES / "chrono24_search_normal.json").read_text(encoding="utf-8"))
    client = FakeChrono24Client(payload)
    assert client.search_items("rolex")["total"] == 1


def test_records_query_page_filters() -> None:
    client = FakeChrono24Client({"items": [], "total": 0})
    client.search_items("submariner", page=2, page_size=10, filters={"brand": "ROLEX"})
    assert client.last_query == "submariner"
    assert client.last_page == 2
    assert client.last_filters == {"brand": "ROLEX"}


def test_call_count() -> None:
    client = FakeChrono24Client({"items": [], "total": 0})
    client.search_items("a")
    client.search_items("b")
    assert client.call_count == 2


def test_injected_exception() -> None:
    client = FakeChrono24Client(error=RuntimeError("fail"))
    with pytest.raises(RuntimeError):
        client.search_items("x")


def test_multi_page() -> None:
    p1 = json.loads((FIXTURES / "chrono24_search_page_1.json").read_text(encoding="utf-8"))
    p2 = json.loads((FIXTURES / "chrono24_search_page_2.json").read_text(encoding="utf-8"))
    client = FakeChrono24Client(pages={1: p1, 2: p2})
    assert client.search_items("rolex", page=2)["page"] == 2


def test_defensive_copy() -> None:
    payload = {"items": [], "total": 0, "page": 1}
    client = FakeChrono24Client(payload)
    result = client.search_items("x")
    result["total"] = 99
    assert client.search_items("x")["total"] == 0
