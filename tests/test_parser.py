"""Unit tests for utils.parser."""

from bs4 import BeautifulSoup

from utils.parser import (
    extract_currency,
    extract_json_ld_blocks,
    extract_text,
    filter_json_ld_by_type,
    normalize_url,
    parse_html,
    parse_price,
    parse_price_with_currency,
    safe_dict_get,
)


def test_parse_html_returns_beautifulsoup() -> None:
    soup = parse_html("<html><body><p>Hello</p></body></html>")
    assert soup.p.get_text(strip=True) == "Hello"


def test_extract_text_with_none() -> None:
    assert extract_text(None, default="fallback") == "fallback"


def test_parse_price_variants() -> None:
    assert parse_price("$1,234.56") == 1234.56
    assert parse_price("€999") == 999.0
    assert parse_price("") is None
    assert parse_price("invalid") is None


def test_extract_currency() -> None:
    assert extract_currency("$890.00") == "USD"
    assert extract_currency("€450.00") == "EUR"
    assert extract_currency("1200 JPY") == "JPY"
    assert extract_currency("no currency") is None


def test_parse_price_with_currency() -> None:
    amount, currency = parse_price_with_currency("$599.00")
    assert amount == 599.0
    assert currency == "USD"


def test_normalize_url_absolute_and_relative() -> None:
    base = "https://www.cettire.com"
    assert normalize_url(base, "https://example.com/item") == "https://example.com/item"
    assert normalize_url(base, "/products/item") == "https://www.cettire.com/products/item"
    assert normalize_url(base, "") == ""


def test_safe_dict_get_nested_path() -> None:
    data = {"offers": {"price": "100", "priceCurrency": "USD"}}
    assert safe_dict_get(data, "offers", "price") == "100"
    assert safe_dict_get(data, "offers", "missing", default="x") == "x"


def test_extract_json_ld_blocks() -> None:
    html = """
    <html><head>
    <script type="application/ld+json">
    [{"@type": "Product", "name": "Bag"}, {"@type": "WebPage", "name": "Search"}]
    </script>
    </head></html>
    """
    soup = parse_html(html)
    blocks = extract_json_ld_blocks(soup)
    assert len(blocks) == 2
    products = filter_json_ld_by_type(blocks, "Product")
    assert len(products) == 1
    assert products[0]["name"] == "Bag"


def test_extract_json_ld_graph_format() -> None:
    html = """
    <script type="application/ld+json">
    {"@graph": [{"@type": "Product", "name": "Shoe"}]}
    </script>
    """
    soup = BeautifulSoup(html, "lxml")
    blocks = extract_json_ld_blocks(soup)
    assert blocks[0]["name"] == "Shoe"
