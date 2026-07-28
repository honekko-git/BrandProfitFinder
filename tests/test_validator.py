"""Unit tests for utils.validator."""

from models.product import Product
from utils.validator import (
    is_positive_number,
    is_valid_product,
    is_valid_url,
    sanitize_query,
    validate_scraped_product,
)


def test_is_valid_url() -> None:
    assert is_valid_url("https://www.cettire.com/products/item") is True
    assert is_valid_url("http://example.com") is True
    assert is_valid_url("not-a-valid-url") is False
    assert is_valid_url("") is False


def test_is_positive_number() -> None:
    assert is_positive_number(10) is True
    assert is_positive_number(0) is False
    assert is_positive_number(None) is False
    assert is_positive_number("bad") is False


def test_sanitize_query() -> None:
    assert sanitize_query("  gucci   bag  ") == "gucci bag"
    assert len(sanitize_query("x" * 300, max_length=200)) == 200


def test_validate_scraped_product_valid() -> None:
    valid, reason = validate_scraped_product(
        name="Leather Bag",
        brand="Gucci",
        price=890.0,
        url="https://www.cettire.com/products/bag",
        sku="GUC-001",
    )
    assert valid is True
    assert reason == ""


def test_validate_scraped_product_missing_name() -> None:
    valid, reason = validate_scraped_product(name="", price=100.0)
    assert valid is False
    assert "name" in reason


def test_validate_scraped_product_negative_price() -> None:
    valid, reason = validate_scraped_product(name="Bag", price=-1.0)
    assert valid is False
    assert "negative" in reason


def test_validate_scraped_product_invalid_url() -> None:
    valid, reason = validate_scraped_product(
        name="Bag",
        price=100.0,
        url="not-a-valid-url",
    )
    assert valid is False
    assert "invalid product URL" in reason


def test_is_valid_product() -> None:
    assert is_valid_product(Product(name="Bag", price=100.0)) is True
    assert is_valid_product(Product(name="", price=100.0)) is False
