"""Unit tests for scanner.baltini (local HTML fixtures only)."""

from pathlib import Path
from unittest.mock import patch

import pytest

from models.product import Product
from scanner.baltini import BaltiniScanner
from scanner.scanner_factory import create_scanner

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "baltini_search_results.html"

HTML_ONLY_FIXTURE = """
<html><body>
  <div class="product-item">
    <a class="product-item__link" href="/products/html-item-a">
      <img class="product-item__image" src="/images/a.jpg">
      <span class="product-item__vendor">Brand A</span>
      <h2 class="product-item__title">HTML Item A</h2>
      <span class="price-item--regular">€100.00</span>
      <span data-product-sku="HTML-A"></span>
    </a>
  </div>
  <div class="product-item">
    <a class="product-item__link" href="/products/html-item-b">
      <span class="product-item__vendor">Brand B</span>
      <h2 class="product-item__title">HTML Item B</h2>
      <span class="price-item--sale">€200.00</span>
      <span class="price-item--regular">€250.00</span>
      <span class="product-sku">HTML-B</span>
    </a>
  </div>
</body></html>
"""


@pytest.fixture
def scanner() -> BaltiniScanner:
    return BaltiniScanner()


@pytest.fixture
def fixture_html() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def test_store_name(scanner: BaltiniScanner) -> None:
    assert scanner.store_name == "Baltini"


def test_parse_products_from_json_ld(scanner: BaltiniScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    names = {product.name for product in products}
    assert "Silk Scarf" in names
    assert "Leather Belt" in names
    assert "Sale Jacket" in names

    scarf = next(product for product in products if product.sku == "HER-001")
    assert scarf.brand == "Hermès"
    assert scarf.price == 320.0
    assert scarf.currency == "EUR"
    assert scarf.url == "https://www.baltini.com/products/silk-scarf"
    assert scarf.image_url == "https://www.baltini.com/images/scarf.jpg"
    assert scarf.in_stock is True
    assert scarf.store_name == "Baltini"

    belt = next(product for product in products if product.sku == "GUC-101")
    assert belt.in_stock is False
    assert belt.url == "https://www.baltini.com/products/leather-belt"
    assert belt.image_url == "https://www.baltini.com/images/belt.jpg"


def test_parse_products_from_html_only(scanner: BaltiniScanner) -> None:
    products = scanner.parse_products(HTML_ONLY_FIXTURE, limit=50)
    assert len(products) == 2
    assert all(isinstance(product, Product) for product in products)

    item_a = next(product for product in products if product.name == "HTML Item A")
    assert item_a.price == 100.0
    assert item_a.sku == "HTML-A"
    assert item_a.url == "https://www.baltini.com/products/html-item-a"
    assert item_a.image_url == "https://www.baltini.com/images/a.jpg"

    item_b = next(product for product in products if product.name == "HTML Item B")
    assert item_b.sale_price == 200.0
    assert item_b.original_price == 250.0
    assert item_b.price == 200.0


def test_parse_products_html_fallback(scanner: BaltiniScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    names = {product.name for product in products}
    assert "Cashmere Sweater" in names
    assert "Sale Boots" in names

    sweater = next(product for product in products if product.name == "Cashmere Sweater")
    assert sweater.brand == "Loro Piana"
    assert sweater.price == 1450.0
    assert sweater.url == "https://www.baltini.com/products/cashmere-sweater"


def test_relative_url_normalization(scanner: BaltiniScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    belt = next(product for product in products if product.sku == "GUC-101")
    assert belt.url.startswith("https://www.baltini.com/")


def test_image_url_normalization(scanner: BaltiniScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    belt = next(product for product in products if product.sku == "GUC-101")
    assert belt.image_url == "https://www.baltini.com/images/belt.jpg"


def test_deduplicate_by_url(scanner: BaltiniScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    scarf_urls = [product.url for product in products if "silk-scarf" in product.url]
    assert len(scarf_urls) == 1


def test_deduplicate_by_sku(scanner: BaltiniScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    dup_products = [product for product in products if product.sku == "DUP-900"]
    assert len(dup_products) == 1


def test_regular_price_only_product(scanner: BaltiniScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    sweater = next(product for product in products if product.name == "Cashmere Sweater")
    assert sweater.price == 1450.0
    assert sweater.sale_price is None
    assert sweater.original_price is None or sweater.original_price == 1450.0


def test_sale_product_prices(scanner: BaltiniScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    boots = next(product for product in products if product.name == "Sale Boots")
    assert boots.sale_price == 420.0
    assert boots.original_price == 560.0
    assert boots.price == 420.0

    jacket = next(product for product in products if product.sku == "MON-200")
    assert jacket.sale_price == 650.0
    assert jacket.original_price == 900.0
    assert jacket.price == 650.0


def test_skip_invalid_price(scanner: BaltiniScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    names = {product.name for product in products}
    assert "Invalid Price Item" not in names


def test_missing_brand(scanner: BaltiniScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    item = next(product for product in products if product.name == "No Brand Item")
    assert item.brand == "Unknown"


def test_missing_image(scanner: BaltiniScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    item = next(product for product in products if product.name == "No Image Item")
    assert item.image_url == ""


def test_inverted_sale_price_handling(scanner: BaltiniScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    item = next(product for product in products if product.name == "Inverted Sale Item")
    assert item.sale_price == 600.0
    assert item.original_price == 900.0
    assert item.price == 600.0


def test_parse_products_empty_html(scanner: BaltiniScanner) -> None:
    assert scanner.parse_products("<html><body></body></html>") == []


def test_parse_products_malformed_html(scanner: BaltiniScanner) -> None:
    products = scanner.parse_products("<not>valid<html", limit=50)
    assert isinstance(products, list)


def test_no_network_access(scanner: BaltiniScanner, fixture_html: str) -> None:
    with patch("utils.http.fetch_url") as mock_fetch, patch("utils.http.HttpClient") as mock_client:
        products = scanner.parse_products(fixture_html, limit=50)
        assert products
        mock_fetch.assert_not_called()
        mock_client.assert_not_called()
        assert scanner.scan("prada bag") == []


def test_factory_creates_baltini_scanner() -> None:
    scanner = create_scanner("baltini")
    assert isinstance(scanner, BaltiniScanner)
    assert scanner.store_name == "Baltini"


def test_factory_store_name_normalization() -> None:
    scanner = create_scanner("  BALTINI  ")
    assert isinstance(scanner, BaltiniScanner)
    assert scanner.store_name == "Baltini"


def test_parse_products_skips_invalid_entries(scanner: BaltiniScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    names = {product.name for product in products}
    assert "" not in names
    assert "Broken URL Item" not in names


def test_parse_products_returns_product_objects(
    scanner: BaltiniScanner, fixture_html: str
) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    assert products
    assert all(isinstance(product, Product) for product in products)


def test_scan_returns_empty_without_network(scanner: BaltiniScanner) -> None:
    assert scanner.scan("prada bag") == []
