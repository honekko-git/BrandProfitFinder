"""Tests for Vestiaire supplier fixture client."""

from __future__ import annotations

from supplier.models import SupplierType
from supplier.vestiaire.client import VestiaireClient


def test_vestiaire_client_search_products_returns_fixture_results() -> None:
    client = VestiaireClient()

    results = client.search_products("chanel wallet", max_results=5)

    assert len(results) == 1
    assert results[0].supplier_name == "vestiaire"
    assert results[0].brand == "Chanel"
    assert results[0].condition == SupplierType.USED.value
    assert results[0].external_id == "vc-chanel-wallet-001"


def test_vestiaire_client_search_products_supports_brand_queries() -> None:
    client = VestiaireClient()

    chanel_results = client.search_products("Chanel")
    hermes_results = client.search_products("Hermes")
    lv_results = client.search_products("Louis Vuitton")

    assert len(chanel_results) == 1
    assert chanel_results[0].brand == "Chanel"
    assert len(hermes_results) == 1
    assert hermes_results[0].brand == "Hermes"
    assert len(lv_results) == 1
    assert lv_results[0].brand == "Louis Vuitton"


def test_vestiaire_client_search_products_paginates_results() -> None:
    client = VestiaireClient()

    first_page = client.search_products("", page=1, max_results=2)
    second_page = client.search_products("", page=2, max_results=2)

    assert len(first_page) == 2
    assert len(second_page) == 1
    assert first_page[0].external_id != second_page[0].external_id
