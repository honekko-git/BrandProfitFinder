"""Unit tests for scanner.italist (local HTML fixtures only)."""

from pathlib import Path
from unittest.mock import patch

import pytest

from models.product import Product
from scanner.italist import ItalistScanner
from scanner.scanner_factory import create_scanner

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "italist_search_results.html"

HTML_ONLY_FIXTURE = """
<html><body>
  <div class="product-tile">
    <a class="product-tile__link" href="/products/html-item-a">
      <img class="product-tile__image" src="/images/a.jpg">
      <span class="product-tile__brand">Brand A</span>
      <h2 class="product-tile__title">HTML Item A</h2>
      <span class="product-tile__price">€100.00</span>
      <span data-product-sku="HTML-A"></span>
    </a>
  </div>
  <div class="product-tile">
    <a class="product-tile__link" href="/products/html-item-b">
      <span class="product-tile__brand">Brand B</span>
      <h2 class="product-tile__title">HTML Item B</h2>
      <span class="product-tile__sale-price">€200.00</span>
      <span class="product-tile__original-price">€250.00</span>
      <span class="product-sku">HTML-B</span>
    </a>
  </div>
</body></html>
"""

PRODUCT_ARRAY_FIXTURE = """
<html><head>
<script type="application/ld+json">
[
  {
    "@type": "Product",
    "name": "Array Product One",
    "brand": {"@type": "Brand", "name": "Fendi"},
    "sku": "ARR-001",
    "image": "/images/array-one.jpg",
    "offers": {
      "price": "780.00",
      "priceCurrency": "EUR",
      "availability": "InStock",
      "url": "/products/array-product-one"
    }
  },
  {
    "@type": "Product",
    "name": "Array Product Two",
    "brand": {"@type": "Brand", "name": "Givenchy"},
    "sku": "ARR-002",
    "image": "https://www.italist.com/images/array-two.jpg",
    "offers": {
      "price": "540.00",
      "priceCurrency": "EUR",
      "availability": "OutOfStock",
      "url": "https://www.italist.com/products/array-product-two"
    }
  }
]
</script>
</head><body></body></html>
"""

OFFERS_LIST_FIXTURE = """
<html><head>
<script type="application/ld+json">
{
  "@type": "Product",
  "name": "Offers List Product",
  "brand": {"@type": "Brand", "name": "Loewe"},
  "sku": "OFF-001",
  "image": "/images/offers-list.jpg",
  "offers": [
    {
      "price": "999.00",
      "priceCurrency": "EUR",
      "availability": "https://schema.org/OutOfStock",
      "url": "/products/offers-list-unavailable"
    },
    {
      "price": "650.00",
      "priceCurrency": "EUR",
      "availability": "https://schema.org/InStock",
      "url": "/products/offers-list-product"
    }
  ]
}
</script>
</head><body></body></html>
"""


@pytest.fixture
def scanner() -> ItalistScanner:
    return ItalistScanner()


@pytest.fixture
def fixture_html() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def test_store_name(scanner: ItalistScanner) -> None:
    assert scanner.store_name == "Italist"


def test_parse_products_from_item_list(scanner: ItalistScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    names = {product.name for product in products}
    assert "Designer Handbag" in names
    assert "Classic Pumps" in names
    assert "PreOrder Coat" in names

    handbag = next(product for product in products if product.sku == "ITA-001")
    assert handbag.brand == "Bottega Veneta"
    assert handbag.price == 2100.0
    assert handbag.currency == "EUR"
    assert handbag.url == "https://www.italist.com/products/designer-handbag"
    assert handbag.image_url == "https://www.italist.com/images/handbag.jpg"
    assert handbag.in_stock is True
    assert handbag.store_name == "Italist"


def test_parse_products_from_product_array(scanner: ItalistScanner) -> None:
    products = scanner.parse_products(PRODUCT_ARRAY_FIXTURE, limit=50)
    assert len(products) == 2

    one = next(product for product in products if product.sku == "ARR-001")
    assert one.name == "Array Product One"
    assert one.price == 780.0
    assert one.in_stock is True
    assert one.url == "https://www.italist.com/products/array-product-one"
    assert one.image_url == "https://www.italist.com/images/array-one.jpg"

    two = next(product for product in products if product.sku == "ARR-002")
    assert two.in_stock is False
    assert two.url == "https://www.italist.com/products/array-product-two"


def test_parse_products_from_html_only(scanner: ItalistScanner) -> None:
    products = scanner.parse_products(HTML_ONLY_FIXTURE, limit=50)
    assert len(products) == 2
    assert all(isinstance(product, Product) for product in products)

    item_a = next(product for product in products if product.name == "HTML Item A")
    assert item_a.price == 100.0
    assert item_a.sku == "HTML-A"
    assert item_a.url == "https://www.italist.com/products/html-item-a"

    item_b = next(product for product in products if product.name == "HTML Item B")
    assert item_b.sale_price == 200.0
    assert item_b.original_price == 250.0
    assert item_b.price == 200.0


def test_parse_products_html_fallback(scanner: ItalistScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    names = {product.name for product in products}
    assert "Linen Dress" in names
    assert "Sale Sneakers" in names

    dress = next(product for product in products if product.name == "Linen Dress")
    assert dress.brand == "Brunello Cucinelli"
    assert dress.price == 890.0
    assert dress.url == "https://www.italist.com/products/linen-dress"


def test_relative_url_normalization(scanner: ItalistScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    pumps = next(product for product in products if product.sku == "ITA-002")
    assert pumps.url == "https://www.italist.com/products/classic-pumps"


def test_image_url_normalization(scanner: ItalistScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    pumps = next(product for product in products if product.sku == "ITA-002")
    assert pumps.image_url == "https://www.italist.com/images/pumps.jpg"


def test_deduplicate_by_url(scanner: ItalistScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    handbag_urls = [product.url for product in products if "designer-handbag" in product.url]
    assert len(handbag_urls) == 1


def test_deduplicate_by_sku(scanner: ItalistScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    dup_products = [product for product in products if product.sku == "ITA-900"]
    assert len(dup_products) == 1


def test_regular_price_only_product(scanner: ItalistScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    dress = next(product for product in products if product.name == "Linen Dress")
    assert dress.price == 890.0
    assert dress.sale_price is None


def test_sale_product_prices(scanner: ItalistScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    sneakers = next(product for product in products if product.name == "Sale Sneakers")
    assert sneakers.sale_price == 350.0
    assert sneakers.original_price == 420.0
    assert sneakers.price == 350.0

    coat = next(product for product in products if product.sku == "ITA-003")
    assert coat.sale_price == 1200.0
    assert coat.original_price == 1500.0
    assert coat.price == 1200.0


def test_inverted_sale_price_handling(scanner: ItalistScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    item = next(product for product in products if product.name == "Inverted Sale Item")
    assert item.sale_price == 350.0
    assert item.original_price == 500.0
    assert item.price == 350.0


def test_skip_invalid_price(scanner: ItalistScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    names = {product.name for product in products}
    assert "Invalid Price Item" not in names


def test_missing_brand(scanner: ItalistScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    item = next(product for product in products if product.name == "No Brand Item")
    assert item.brand == "Unknown"


def test_missing_image(scanner: ItalistScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    item = next(product for product in products if product.name == "No Image Item")
    assert item.image_url == ""


def test_parse_products_empty_html(scanner: ItalistScanner) -> None:
    assert scanner.parse_products("<html><body></body></html>") == []


def test_parse_products_malformed_html(scanner: ItalistScanner) -> None:
    products = scanner.parse_products("<not>valid<html", limit=50)
    assert isinstance(products, list)


def test_offers_list_parsing(scanner: ItalistScanner) -> None:
    products = scanner.parse_products(OFFERS_LIST_FIXTURE, limit=50)
    assert len(products) == 1
    product = products[0]
    assert product.name == "Offers List Product"
    assert product.price == 650.0
    assert product.in_stock is True
    assert product.url == "https://www.italist.com/products/offers-list-product"


def test_availability_normalization(scanner: ItalistScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    handbag = next(product for product in products if product.sku == "ITA-001")
    pumps = next(product for product in products if product.sku == "ITA-002")
    coat = next(product for product in products if product.sku == "ITA-003")

    assert handbag.in_stock is True
    assert pumps.in_stock is False
    assert coat.in_stock is True


def test_no_network_access(scanner: ItalistScanner, fixture_html: str) -> None:
    with patch("utils.http.fetch_url") as mock_fetch, patch("utils.http.HttpClient") as mock_client:
        products = scanner.parse_products(fixture_html, limit=50)
        assert products
        mock_fetch.assert_not_called()
        mock_client.assert_not_called()
        assert scanner.scan("gucci bag") == []


def test_factory_creates_italist_scanner() -> None:
    scanner = create_scanner("italist")
    assert isinstance(scanner, ItalistScanner)
    assert scanner.store_name == "Italist"


def test_factory_store_name_normalization() -> None:
    scanner = create_scanner("  ITALIST  ")
    assert isinstance(scanner, ItalistScanner)
    assert scanner.store_name == "Italist"


def test_parse_products_skips_invalid_entries(scanner: ItalistScanner, fixture_html: str) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    names = {product.name for product in products}
    assert "" not in names
    assert "Broken URL Item" not in names


def test_parse_products_returns_product_objects(
    scanner: ItalistScanner, fixture_html: str
) -> None:
    products = scanner.parse_products(fixture_html, limit=50)
    assert products
    assert all(isinstance(product, Product) for product in products)


def test_scan_returns_empty_without_network(scanner: ItalistScanner) -> None:
    assert scanner.scan("gucci bag") == []
