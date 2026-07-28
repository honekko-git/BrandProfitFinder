"""
Baltini store scanner.
"""

import logging
from urllib.parse import quote_plus

from bs4 import Tag

from config.constants import (
    BALTINI_BASE_URL,
    COUNTRY_IT,
    CURRENCY_EUR,
    DEFAULT_SCAN_LIMIT,
    STORE_BALTINI,
)
from models.product import Product
from scanner.base_scanner import BaseScanner
from utils.parser import extract_text, get_attr, normalize_url, parse_html, parse_price

logger = logging.getLogger(__name__)


class BaltiniScanner(BaseScanner):
    """Scanner implementation for Baltini."""

    PRODUCT_SELECTORS = [
        "div.product-item",
        "li.product",
        "article.product-card",
        "div.grid__item",
    ]
    NAME_SELECTORS = [
        ".product-item__title",
        ".product-title",
        "h2.card__heading",
        "a.full-unstyled-link",
    ]
    BRAND_SELECTORS = [
        ".product-item__vendor",
        ".product-vendor",
        ".card__vendor",
    ]
    PRICE_SELECTORS = [
        ".price-item--sale",
        ".price",
        ".product-price",
        "[data-product-price]",
    ]
    LINK_SELECTORS = [
        "a.product-item__link",
        "a.full-unstyled-link",
        "a[href*='/products/']",
    ]
    IMAGE_SELECTORS = ["img.product-item__image", "img[src]", "img[data-src]"]

    @property
    def store_name(self) -> str:
        return STORE_BALTINI

    @property
    def country(self) -> str:
        return COUNTRY_IT

    @property
    def base_url(self) -> str:
        return BALTINI_BASE_URL

    @property
    def default_currency(self) -> str:
        return CURRENCY_EUR

    def build_search_url(self, query: str) -> str:
        encoded = quote_plus(query)
        return f"{self.base_url}/search?q={encoded}"

    def scan(self, query: str, limit: int = DEFAULT_SCAN_LIMIT) -> list[Product]:
        """
        Collect products for the given query.

        Network fetching is not performed in this phase; use parse_products().

        Args:
            query: Search keywords.
            limit: Maximum number of products to return.

        Returns:
            Empty list. HTML parsing is handled by parse_products().
        """
        logger.warning(
            "%s scan() does not fetch remote HTML; use parse_products() with local HTML",
            self.store_name,
        )
        return []

    def parse_products(self, html: str, limit: int = DEFAULT_SCAN_LIMIT) -> list[Product]:
        soup = parse_html(html)
        cards = self._find_product_cards(soup)
        products: list[Product] = []

        for card in cards:
            if len(products) >= limit:
                break
            product = self._parse_card(card)
            if product is not None:
                products.append(product)

        deduplicated = self._deduplicate_products(products)
        result = deduplicated[:limit]
        logger.debug("Baltini parsed %d products from HTML", len(result))
        return result

    def _find_product_cards(self, soup) -> list[Tag]:
        for selector in self.PRODUCT_SELECTORS:
            cards = soup.select(selector)
            if cards:
                return cards
        return soup.select("a[href*='/products/']")

    def _parse_card(self, card: Tag) -> Product | None:
        name = self._extract_from_selectors(card, self.NAME_SELECTORS)
        brand = self._extract_from_selectors(card, self.BRAND_SELECTORS) or "Unknown"
        price_text = self._extract_from_selectors(card, self.PRICE_SELECTORS)
        price = parse_price(price_text)

        link_el = self._first_element(card, self.LINK_SELECTORS)
        href = get_attr(link_el, "href")
        url = normalize_url(self.base_url, href)

        if not name and link_el is not None:
            name = extract_text(link_el)

        image_el = self._first_element(card, self.IMAGE_SELECTORS)
        image_url = get_attr(image_el, "data-src") or get_attr(image_el, "src")
        image_url = normalize_url(self.base_url, image_url)

        if not name or price is None:
            return None

        return self._make_product(
            name=name,
            brand=brand,
            price=price,
            currency=self.default_currency,
            url=url,
            image_url=image_url,
        )

    def _extract_from_selectors(self, card: Tag, selectors: list[str]) -> str:
        for selector in selectors:
            element = card.select_one(selector)
            text = extract_text(element)
            if text:
                return text
        return ""

    def _first_element(self, card: Tag, selectors: list[str]) -> Tag | None:
        for selector in selectors:
            element = card.select_one(selector)
            if element is not None:
                return element
        return None
