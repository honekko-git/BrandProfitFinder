"""Tests for Open Graph saved HTML parser."""

from __future__ import annotations

from marketplace.acquisition_workspace.saved_html_parser import GenericOpenGraphParser


def test_open_graph_title_price_image_url() -> None:
    html = """
    <html><head>
      <meta property="og:title" content="Chanel Wallet Black">
      <meta property="product:price:amount" content="695.00">
      <meta property="product:price:currency" content="USD">
      <meta property="og:url" content="https://example.com/wallet">
      <meta property="og:image" content="https://example.com/image.jpg">
    </head></html>
    """
    parser = GenericOpenGraphParser()
    assert parser.can_parse(html)
    parsed = parser.parse(html)
    assert len(parsed) == 1
    assert parsed[0].title == "Chanel Wallet Black"
    assert parsed[0].purchase_price == 695
    assert parsed[0].currency == "USD"
    assert parsed[0].purchase_url == "https://example.com/wallet"
    assert parsed[0].image_url == "https://example.com/image.jpg"


def test_missing_price_returns_warning() -> None:
    html = '<meta property="og:title" content="Title Only">'
    parsed = GenericOpenGraphParser().parse(html)
    assert parsed[0].warnings == ("missing price",)


def test_missing_title_returns_empty() -> None:
    html = '<meta property="product:price:amount" content="100">'
    parsed = GenericOpenGraphParser().parse(html)
    assert parsed == []
