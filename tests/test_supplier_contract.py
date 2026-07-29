"""Tests for supplier client protocol contract."""

from __future__ import annotations

from supplier.base import SupplierClient
from supplier.models import SupplierProduct, SupplierType


class _StubSupplierClient:
    """In-memory test double for protocol validation only."""

    def __init__(self, supplier_name: str, supplier_type: SupplierType) -> None:
        self._supplier_name = supplier_name
        self._supplier_type = supplier_type

    @property
    def supplier_name(self) -> str:
        return self._supplier_name

    @property
    def supplier_type(self) -> SupplierType:
        return self._supplier_type

    def search_products(
        self,
        query: str,
        *,
        page: int = 1,
        max_results: int = 20,
    ) -> list[SupplierProduct]:
        if not query.strip():
            return []
        return [
            SupplierProduct(
                supplier_name=self._supplier_name,
                external_id=f"{self._supplier_name}-1",
                title=f"{query} sample",
                brand="Sample Brand",
                category="bags",
                condition="used" if self._supplier_type is SupplierType.USED else "new",
                purchase_price=500.0,
                currency="USD",
                url=f"https://example.test/{self._supplier_name}/1",
                image_urls=[],
                availability="in_stock",
            )
        ][:max_results]


def test_supplier_client_protocol_compatibility() -> None:
    client = _StubSupplierClient("stub-supplier", SupplierType.NEW)

    assert isinstance(client, SupplierClient)
    assert client.supplier_name == "stub-supplier"
    assert client.supplier_type is SupplierType.NEW


def test_supplier_client_search_contract() -> None:
    client = _StubSupplierClient("used-supplier", SupplierType.USED)

    results = client.search_products("gucci bag", page=1, max_results=5)

    assert len(results) == 1
    assert results[0].title == "gucci bag sample"
    assert results[0].condition == "used"
    assert results[0].supplier_name == "used-supplier"


def test_supplier_client_search_respects_empty_query() -> None:
    client = _StubSupplierClient("stub-supplier", SupplierType.NEW)

    assert client.search_products("   ") == []
