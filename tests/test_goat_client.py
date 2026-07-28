"""Tests for GOAT fake client."""

import json
from pathlib import Path

import pytest

from marketplace.goat_client import FakeGoatClient

FIXTURES = Path(__file__).parent / "fixtures"


def test_fixture_return() -> None:
    payload = json.loads((FIXTURES / "goat_search_normal.json").read_text(encoding="utf-8"))
    client = FakeGoatClient(payload)
    assert client.search_items("gucci")["total"] == 3


def test_stable_ordering() -> None:
    payload = json.loads((FIXTURES / "goat_search_normal.json").read_text(encoding="utf-8"))
    client = FakeGoatClient(payload)
    first = client.search_items("demo")
    second = client.search_items("demo")
    assert first["items"] == second["items"]


def test_records_query_page_filters() -> None:
    client = FakeGoatClient({"items": [], "total": 0, "page": 1})
    client.search_items("dunk", page=2, page_size=10, filters={"brand": "NIKE"})
    assert client.last_query == "dunk"
    assert client.last_page == 2
    assert client.last_filters == {"brand": "NIKE"}


def test_call_count() -> None:
    client = FakeGoatClient({"items": [], "total": 0, "page": 1})
    client.search_items("a")
    client.search_items("b")
    assert client.call_count == 2


def test_injected_exception() -> None:
    client = FakeGoatClient(error=RuntimeError("fail"))
    with pytest.raises(RuntimeError):
        client.search_items("x")


def test_multi_page() -> None:
    p1 = json.loads((FIXTURES / "goat_search_normal.json").read_text(encoding="utf-8"))
    p2 = {"marketplace": "goat", "items": [], "total": 0, "page": 2}
    client = FakeGoatClient(pages={1: p1, 2: p2})
    assert client.search_items("demo", page=2)["page"] == 2


def test_defensive_copy() -> None:
    payload = {"items": [], "total": 0, "page": 1}
    client = FakeGoatClient(payload)
    result = client.search_items("x")
    result["total"] = 99
    assert client.search_items("x")["total"] == 0


def test_filter_by_query() -> None:
    payload = json.loads((FIXTURES / "goat_search_normal.json").read_text(encoding="utf-8"))
    client = FakeGoatClient(payload, filter_by_query=True)
    result = client.search_items("PRADA")
    assert result["total"] == 1
    assert "PRADA" in str(result["items"][0].get("brand"))


def test_missing_fixture_page_returns_empty() -> None:
    client = FakeGoatClient({"items": [], "total": 0, "page": 1})
    result = client.search_items("x", page=99)
    assert result["items"] == []
    assert result["total"] == 0


def test_docstring_states_no_network() -> None:
    assert "no network" in FakeGoatClient.__doc__.lower()
    assert "synthetic" in FakeGoatClient.__doc__.lower()
