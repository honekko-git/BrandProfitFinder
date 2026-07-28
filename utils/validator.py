"""
Input validation helpers.
"""

import re
from urllib.parse import urlparse

from models.product import Product


def is_valid_url(url: str) -> bool:
    """
    Check whether a string is a valid HTTP/HTTPS URL.

    Args:
        url: URL string to validate.

    Returns:
        True when URL has http(s) scheme and netloc.
    """
    if not url or not url.strip():
        return False
    parsed = urlparse(url.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def is_positive_number(value: float | int | None) -> bool:
    """
    Check whether a numeric value is positive.

    Args:
        value: Number to validate.

    Returns:
        True when value is a number greater than zero.
    """
    if value is None:
        return False
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def sanitize_query(query: str, max_length: int = 200) -> str:
    """
    Normalize a search query string.

    Args:
        query: Raw search query.
        max_length: Maximum allowed length.

    Returns:
        Sanitized query string.
    """
    cleaned = re.sub(r"\s+", " ", query.strip())
    return cleaned[:max_length]


def validate_scraped_product(
    name: str,
    brand: str = "",
    price: float | None = None,
    url: str = "",
    sku: str = "",
) -> tuple[bool, str]:
    """
    Validate scraped product fields before creating a Product instance.

    Args:
        name: Product name.
        brand: Brand name.
        price: Listed price.
        url: Product page URL.
        sku: Product identifier.

    Returns:
        Tuple of (is_valid, reason). reason is empty when valid.
    """
    if not name or not name.strip():
        return False, "missing product name"

    if price is not None and price < 0:
        return False, f"negative price: {price}"

    if url and url.strip() and not is_valid_url(url):
        return False, f"invalid product URL: {url}"

    if sku and not sku.strip():
        return False, "empty SKU after strip"

    return True, ""


def is_valid_product(product: Product) -> bool:
    """
    Check whether a Product instance has minimum required data.

    Args:
        product: Product to validate.

    Returns:
        True when the product has a non-empty name and non-negative price.
    """
    valid, _ = validate_scraped_product(
        name=product.name,
        brand=product.brand,
        price=product.price,
        url=product.url,
        sku=product.sku,
    )
    return valid
