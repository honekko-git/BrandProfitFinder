"""Tests for Vestiaire fake client."""

import json
from pathlib import Path

import pytest

from marketplace.vestiaire_client import FakeVestiaireClient

FIXTURES = Path(__file__).parent / "fixtures"


def test_fixture_return() -> None:
    payload = json.loads((FIXTURES / "vestiaire_search_normal.json").read_text(encoding="utf-8"))
    client = FakeVestiaireClient(payload)
    result = client.search_items("gucci")
    assert result["total"] == 1


def test_records_query_page_filters() -> None:
    client = FakeVestiaireClient({"items": [], "total": 0})
    client.search_items("bag", page=2, page_size=10, filters={"brand": "GUCCI"})
    assert client.last_query == "bag"
    assert client.last_page == 2
    assert client.last_page_size == 10
    assert client.last_filters == {"brand": "GUCCI"}


def test_call_count() -> None:
    client = FakeVestiaireClient({"items": [], "total": 0})
    client.search_items("a")
    client.search_items("b")
    assert client.call_count == 2


def test_injected_exception() -> None:
    client = FakeVestiaireClient(error=RuntimeError("fail"))
    with pytest.raises(RuntimeError):
        client.search_items("x")


def test_multi_page() -> None:
    p1 = json.loads((FIXTURES / "vestiaire_search_page_1.json").read_text(encoding="utf-8"))
    p2 = json.loads((FIXTURES / "vestiaire_search_page_2.json").read_text(encoding="utf-8"))
    client = FakeVestiaireClient(pages={1: p1, 2: p2})
    assert client.search_items("gucci", page=1)["page"] == 1
    assert client.search_items("gucci", page=2)["page"] == 2
