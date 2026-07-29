"""Tests for overseas new supplier client contract."""

from __future__ import annotations

from supplier.base import SupplierClient
from supplier.models import SupplierProduct, SupplierType
from supplier.overseas_new.base import OverseasNewSupplierClient


class _StubOverseasNewSupplierClient:
    """In-memory test double for overseas new protocol validation only."""

    @property
    def supplier_name(self) -> str:
        return "overseas-new-stub"

    @property
    def supplier_type(self) -> SupplierType:
        return SupplierType.NEW

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
                supplier_name=self.supplier_name,
                external_id=f"{self.supplier_name}-{page}-1",
                title=f"{query} new item",
                brand="Gucci",
                category="bags",
                condition=SupplierType.NEW.value,
                purchase_price=300.0,
                currency="USD",
                url="https://example.test/new/1",
                image_urls=[],
                availability="in_stock",
            )
        ][:max_results]


def test_overseas_new_supplier_protocol_compatibility() -> None:
    client = _StubOverseasNewSupplierClient()

    assert isinstance(client, OverseasNewSupplierClient)
    assert isinstance(client, SupplierClient)
    assert client.supplier_name == "overseas-new-stub"
    assert client.supplier_type is SupplierType.NEW


def test_overseas_new_supplier_search_return_contract() -> None:
    client = _StubOverseasNewSupplierClient()

    results = client.search_products("gucci bag", page=2, max_results=10)

    assert len(results) == 1
    assert results[0].condition == "NEW"
    assert results[0].external_id == "overseas-new-stub-2-1"
    assert results[0].title == "gucci bag new item"
