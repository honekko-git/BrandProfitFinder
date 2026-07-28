"""Unit tests for scanner.cettire (local HTML fixtures only)."""

from pathlib import Path

import pytest

from models.product import Product
from scanner.cettire import CettireScanner

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "cettire_search_results.html"


@pytest.fixture
def scanner() -> CettireScanner:
    return CettireScanner()


@pytest.fixture
def fixture_html() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def test_store_name(scanner: CettireScanner) -> None:
    assert scanner.store_name == "Cettire"


def test_parse_products_returns_product_objects(
    scanner: CettireScanner, fixture_html: str
) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    assert products
    assert all(isinstance(product, Product) for product in products)


def test_parse_products_from_json_ld(scanner: CettireScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    names = {product.name for product in products}
    assert "Leather Tote Bag" in names
    assert "Suede Loafers" in names

    gucci = next(product for product in products if product.sku == "GUC-001")
    assert gucci.brand == "Gucci"
    assert gucci.price == 890.0
    assert gucci.currency == "USD"
    assert gucci.url == "https://www.cettire.com/products/leather-tote-bag"
    assert gucci.image_url == "https://www.cettire.com/images/tote.jpg"
    assert gucci.in_stock is True

    prada = next(product for product in products if product.sku == "PRD-002")
    assert prada.in_stock is False
    assert prada.url == "https://www.cettire.com/products/suede-loafers"
    assert prada.image_url == "https://www.cettire.com/images/loafers.jpg"


def test_parse_products_html_fallback(scanner: CettireScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    names = {product.name for product in products}
    assert "Wool Coat" in names
    assert "Sale Sneakers" in names

    coat = next(product for product in products if product.name == "Wool Coat")
    assert coat.brand == "Burberry"
    assert coat.price == 1200.0
    assert coat.url == "https://www.cettire.com/products/wool-coat"

    sneakers = next(product for product in products if product.name == "Sale Sneakers")
    assert sneakers.sale_price == 599.0
    assert sneakers.original_price == 799.0
    assert sneakers.sku == "BAL-004"


def test_parse_products_deduplicates_by_url(scanner: CettireScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    tote_urls = [
        product.url
        for product in products
        if "leather-tote-bag" in product.url
    ]
    assert len(tote_urls) == 1


def test_parse_products_skips_invalid_entries(scanner: CettireScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    names = {product.name for product in products}
    assert "" not in names
    assert "Broken URL Item" not in names


def test_parse_products_respects_limit(scanner: CettireScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=2)
    assert len(products) == 2


def test_scan_returns_empty_without_network(scanner: CettireScanner) -> None:
    assert scanner.scan("gucci bag") == []


def test_parse_products_empty_html(scanner: CettireScanner) -> None:
    assert scanner.parse_products("<html><body></body></html>") == []
