"""Tests for TheRealReal supplier fixture client."""

from __future__ import annotations

from supplier.models import SupplierType
from supplier.therealreal.client import TheRealRealClient


def test_therealreal_client_search_products_returns_fixture_results() -> None:
    client = TheRealRealClient()

    results = client.search_products("chanel wallet", max_results=5)

    assert len(results) == 1
    assert results[0].supplier_name == "therealreal"
    assert results[0].brand == "Chanel"
    assert results[0].condition == SupplierType.USED.value
    assert results[0].external_id == "trr-chanel-wallet-001"


def test_therealreal_client_search_products_supports_brand_queries() -> None:
    client = TheRealRealClient()

    chanel_results = client.search_products("Chanel")
    gucci_results = client.search_products("Gucci")
    lv_results = client.search_products("Louis Vuitton")

    assert len(chanel_results) == 1
    assert chanel_results[0].brand == "Chanel"
    assert len(gucci_results) == 1
    assert gucci_results[0].brand == "Gucci"
    assert len(lv_results) == 1
    assert lv_results[0].brand == "Louis Vuitton"


def test_therealreal_client_search_products_paginates_results() -> None:
    client = TheRealRealClient()

    first_page = client.search_products("", page=1, max_results=2)
    second_page = client.search_products("", page=2, max_results=2)

    assert len(first_page) == 2
    assert len(second_page) == 1
    assert first_page[0].external_id != second_page[0].external_id
