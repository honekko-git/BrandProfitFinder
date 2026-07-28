"""Tests for Grailed fake client."""

import json
from pathlib import Path

import pytest

from marketplace.grailed_client import FakeGrailedClient

FIXTURES = Path(__file__).parent / "fixtures"


def test_fixture_return() -> None:
    payload = json.loads((FIXTURES / "grailed_search_normal.json").read_text(encoding="utf-8"))
    client = FakeGrailedClient(payload)
    assert client.search_items("rick")["total"] == 1


def test_records_query_page_filters() -> None:
    client = FakeGrailedClient({"items": [], "total": 0})
    client.search_items("sneakers", page=2, page_size=10, filters={"brand": "RO"})
    assert client.last_query == "sneakers"
    assert client.last_page == 2
    assert client.last_page_size == 10
    assert client.last_filters == {"brand": "RO"}


def test_call_count() -> None:
    client = FakeGrailedClient({"items": [], "total": 0})
    client.search_items("a")
    client.search_items("b")
    assert client.call_count == 2


def test_injected_exception() -> None:
    client = FakeGrailedClient(error=RuntimeError("fail"))
    with pytest.raises(RuntimeError):
        client.search_items("x")


def test_multi_page() -> None:
    p1 = json.loads((FIXTURES / "grailed_search_page_1.json").read_text(encoding="utf-8"))
    p2 = json.loads((FIXTURES / "grailed_search_page_2.json").read_text(encoding="utf-8"))
    client = FakeGrailedClient(pages={1: p1, 2: p2})
    assert client.search_items("rick", page=2)["page"] == 2


def test_defensive_copy() -> None:
    payload = {"items": [], "total": 0, "page": 1}
    client = FakeGrailedClient(payload)
    result = client.search_items("x")
    result["total"] = 99
    assert client.search_items("x")["total"] == 0


def test_filters_defensive_copy() -> None:
    client = FakeGrailedClient({"items": [], "total": 0})
    filters = {"brand": "RO"}
    client.search_items("x", filters=filters)
    filters["brand"] = "CHANGED"
    assert client.last_filters == {"brand": "RO"}
