"""Foundation tests for scanner.base_scanner."""

import pytest

from models.product import Product
from scanner.base_scanner import BaseScanner


class _StubScanner(BaseScanner):
    @property
    def store_name(self) -> str:
        return "Stub Store"

    @property
    def country(self) -> str:
        return "US"

    def scan(self, query: str, limit: int = 50) -> list[Product]:
        if not query.strip():
            return []
        return [self.create_product("Stub Item", "Stub Brand", 100.0, "USD")][:limit]


def test_base_scanner_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        BaseScanner()  # type: ignore[abstract]


def test_stub_scanner_returns_products() -> None:
    scanner = _StubScanner()
    products = scanner.scan("demo", limit=1)
    assert len(products) == 1
    assert isinstance(products[0], Product)
    assert products[0].store_name == "Stub Store"


def test_create_product_applies_store_metadata() -> None:
    scanner = _StubScanner()
    product = scanner.create_product("Item", "Brand", 10.0, "USD", url="https://example.com")
    assert product.country == "US"
    assert product.url == "https://example.com"
