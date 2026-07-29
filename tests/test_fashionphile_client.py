"""Tests for Fashionphile supplier client."""

from __future__ import annotations

from supplier.fashionphile.client import FashionphileClient
from supplier.models import SupplierType


def test_fashionphile_client_search_products_returns_used_supplier_products() -> None:
    client = FashionphileClient()

    results = client.search_products("gucci", max_results=5)

    assert len(results) == 1
    assert results[0].supplier_name == "fashionphile"
    assert results[0].brand == "Gucci"
    assert results[0].condition == SupplierType.USED.value


def test_fashionphile_client_search_products_supports_brand_queries() -> None:
    client = FashionphileClient()

    chanel_results = client.search_products("Chanel")
    hermes_results = client.search_products("Hermes")

    assert len(chanel_results) == 2
    assert chanel_results[0].brand == "Chanel"
    assert len(hermes_results) == 1
    assert hermes_results[0].brand == "Hermes"


def test_fashionphile_client_search_products_paginates_results() -> None:
    client = FashionphileClient()

    first_page = client.search_products("", page=1, max_results=2)
    second_page = client.search_products("", page=2, max_results=2)

    assert len(first_page) == 2
    assert len(second_page) == 2
    assert first_page[0].external_id != second_page[0].external_id
