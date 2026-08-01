"""Tests for JSON-LD saved HTML parser."""

from __future__ import annotations

from pathlib import Path

from marketplace.acquisition_workspace.saved_html_parser import GenericProductJsonLdParser

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "browser_acquisition"


def test_single_product_json_ld() -> None:
    html = FIXTURES.joinpath("fashionphile_json_ld.html").read_text(encoding="utf-8")
    parser = GenericProductJsonLdParser()
    assert parser.can_parse(html)
    parsed = parser.parse(html)
    assert len(parsed) == 1
    assert parsed[0].title == "Chanel Classic Wallet Black Caviar"
    assert parsed[0].purchase_price > 0
    assert parsed[0].currency == "USD"
    assert parsed[0].brand == "Chanel"


def test_item_list_and_multiple_products(tmp_path: Path) -> None:
    html = """
    <html><head>
    <script type="application/ld+json">
    {"@type":"ItemList","itemListElement":[
      {"@type":"ListItem","item":{"@type":"Product","name":"Wallet A","offers":{"price":"100","priceCurrency":"USD"},"url":"https://example.com/a"}},
      {"@type":"ListItem","item":{"@type":"Product","name":"Wallet B","offers":{"price":"200","priceCurrency":"USD"},"url":"https://example.com/b"}}
    ]}
    </script></head></html>
    """
    parsed = GenericProductJsonLdParser().parse(html)
    assert len(parsed) == 2


def test_missing_price_warning() -> None:
    html = """
    <script type="application/ld+json">
    {"@type":"Product","name":"No Price Wallet","offers":{"price":"0","priceCurrency":"USD"}}
    </script>
    """
    parsed = GenericProductJsonLdParser().parse(html)
    assert parsed[0].warnings == ("missing price",)


def test_canonical_url_from_entity() -> None:
    html = """
    <script type="application/ld+json">
    {"@type":"Product","name":"Wallet","url":"https://example.com/canonical","offers":{"price":"50","priceCurrency":"USD"}}
    </script>
    """
    parsed = GenericProductJsonLdParser().parse(html)
    assert parsed[0].purchase_url == "https://example.com/canonical"
