"""
HTML and text parsing helpers.
"""

import json
import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

_CURRENCY_SYMBOLS: dict[str, str] = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
    "USD": "USD",
    "EUR": "EUR",
    "GBP": "GBP",
    "JPY": "JPY",
}


def parse_html(html: str) -> BeautifulSoup:
    """
    Parse HTML string into a BeautifulSoup object.

    Args:
        html: Raw HTML content.

    Returns:
        Parsed BeautifulSoup document.
    """
    return BeautifulSoup(html, "lxml")


def extract_text(element: Tag | None, default: str = "") -> str:
    """
    Safely extract stripped text from a BeautifulSoup element.

    Args:
        element: BeautifulSoup tag or None.
        default: Value when element is missing.

    Returns:
        Stripped text content.
    """
    if element is None:
        return default
    return element.get_text(strip=True) or default


def parse_price(raw: str | None) -> float | None:
    """
    Parse a price string into a float.

    Args:
        raw: Price text such as '$1,234.56' or '€999'.

    Returns:
        Parsed price or None when parsing fails.
    """
    if not raw:
        return None

    cleaned = re.sub(r"[^\d.,]", "", raw.strip())
    if not cleaned:
        return None

    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        parts = cleaned.split(",")
        cleaned = (
            cleaned.replace(",", ".")
            if len(parts) == 2 and len(parts[1]) <= 2
            else cleaned.replace(",", "")
        )

    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_currency(raw: str | None) -> str | None:
    """
    Extract an ISO currency code from a price string.

    Args:
        raw: Price text that may contain a currency symbol or code.

    Returns:
        ISO currency code or None when not detected.
    """
    if not raw:
        return None

    text = raw.strip().upper()
    for symbol, code in _CURRENCY_SYMBOLS.items():
        if symbol.upper() in text or symbol in raw:
            return code

    match = re.search(r"\b([A-Z]{3})\b", text)
    if match:
        return match.group(1)

    return None


def parse_price_with_currency(raw: str | None) -> tuple[float | None, str | None]:
    """
    Parse price text into amount and currency code.

    Args:
        raw: Price text such as '$1,234.56 USD'.

    Returns:
        Tuple of (amount, currency_code).
    """
    if not raw:
        return None, None
    return parse_price(raw), extract_currency(raw)


def get_attr(element: Tag | None, attr: str, default: str = "") -> str:
    """
    Safely read an attribute from a BeautifulSoup tag.

    Args:
        element: BeautifulSoup tag or None.
        attr: Attribute name.
        default: Fallback value.

    Returns:
        Attribute value or default.
    """
    if element is None:
        return default
    value = element.get(attr)
    return str(value) if value is not None else default


def first_match(soup: BeautifulSoup, selectors: list[str]) -> Tag | None:
    """
    Return the first element matching any CSS selector in the list.

    Args:
        soup: Parsed HTML document.
        selectors: CSS selectors to try in order.

    Returns:
        First matching tag or None.
    """
    for selector in selectors:
        found = soup.select_one(selector)
        if found is not None:
            return found
    return None


def normalize_url(base_url: str, href: str | None) -> str:
    """
    Build an absolute URL from a base and relative href.

    Absolute URLs are returned unchanged. Root-relative paths (starting with
    ``/``) are joined to the base URL. Other strings are returned as-is so
    downstream validation can reject malformed links.

    Args:
        base_url: Store base URL.
        href: Relative or absolute link.

    Returns:
        Absolute URL string, or the original href when it cannot be normalized.
    """
    if not href:
        return ""
    href = href.strip()
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("/"):
        return urljoin(base_url.rstrip("/") + "/", href)
    return href


def safe_dict_get(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """
    Traverse nested dict keys safely.

    Args:
        data: Source dictionary.
        keys: Key path to traverse.
        default: Value when path is missing.

    Returns:
        Nested value or default.
    """
    current: Any = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def extract_json_ld_blocks(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """
    Extract JSON-LD objects from script tags in a parsed document.

    Args:
        soup: Parsed HTML document.

    Returns:
        List of JSON-LD dictionary objects.
    """
    blocks: list[dict[str, Any]] = []
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text(strip=True)
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        blocks.extend(_flatten_json_ld(parsed))
    return blocks


def filter_json_ld_by_type(
    blocks: list[dict[str, Any]], schema_type: str
) -> list[dict[str, Any]]:
    """
    Filter JSON-LD blocks by @type value.

    Args:
        blocks: Parsed JSON-LD objects.
        schema_type: Schema.org type name such as 'Product'.

    Returns:
        Matching JSON-LD objects.
    """
    matches: list[dict[str, Any]] = []
    for block in blocks:
        block_type = block.get("@type", "")
        if isinstance(block_type, list):
            if schema_type in block_type:
                matches.append(block)
        elif block_type == schema_type:
            matches.append(block)
    return matches


def _flatten_json_ld(parsed: Any) -> list[dict[str, Any]]:
    """Normalize JSON-LD payload into a flat list of dict objects."""
    if isinstance(parsed, dict):
        graph = parsed.get("@graph")
        if isinstance(graph, list):
            return [item for item in graph if isinstance(item, dict)]
        return [parsed]
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    return []
