"""Tests for Fashionphile fake client."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from marketplace.fashionphile_client import FakeFashionphileClient

FIXTURES = Path(__file__).parent / "fixtures"


def test_fixture_return() -> None:
    payload = json.loads((FIXTURES / "fashionphile_search_normal.json").read_text(encoding="utf-8"))
    client = FakeFashionphileClient(payload)
    result = client.search_items("gucci")
    assert result["total"] == 1


def test_records_query_page_filters() -> None:
    client = FakeFashionphileClient({"items": [], "total": 0})
    client.search_items("bag", page=2, page_size=10, filters={"brand": "GUCCI"})
    assert client.last_query == "bag"
    assert client.last_page == 2
    assert client.last_page_size == 10
    assert client.last_filters == {"brand": "GUCCI"}


def test_call_count() -> None:
    client = FakeFashionphileClient({"items": [], "total": 0})
    client.search_items("a")
    client.search_items("b")
    assert client.call_count == 2


def test_injected_exception() -> None:
    client = FakeFashionphileClient(error=RuntimeError("fail"))
    with pytest.raises(RuntimeError):
        client.search_items("x")


def test_multi_page() -> None:
    p1 = json.loads((FIXTURES / "fashionphile_search_page_1.json").read_text(encoding="utf-8"))
    p2 = json.loads((FIXTURES / "fashionphile_search_page_2.json").read_text(encoding="utf-8"))
    client = FakeFashionphileClient(pages={1: p1, 2: p2})
    assert client.search_items("gucci", page=1)["page"] == 1
    assert client.search_items("gucci", page=2)["page"] == 2


def test_defensive_copy_on_return() -> None:
    payload = {"items": [], "total": 0, "page": 1}
    client = FakeFashionphileClient(payload)
    result = client.search_items("x")
    result["total"] = 99
    assert client.search_items("x")["total"] == 0


def test_defensive_copy_on_filters() -> None:
    client = FakeFashionphileClient({"items": [], "total": 0})
    filters = {"brand": "GUCCI"}
    client.search_items("x", filters=filters)
    filters["brand"] = "CHANGED"
    assert client.last_filters == {"brand": "GUCCI"}


def test_set_payload_copies() -> None:
    payload = {"items": [], "total": 1}
    client = FakeFashionphileClient()
    client.set_payload(payload)
    payload["total"] = 99
    assert client.search_items("x")["total"] == 1
