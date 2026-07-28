"""
Cettire store scanner.
"""

import logging
from typing import Any
from urllib.parse import quote_plus

from bs4 import BeautifulSoup, Tag

from config.constants import (
    CETTIRE_BASE_URL,
    COUNTRY_US,
    CURRENCY_USD,
    DEFAULT_SCAN_LIMIT,
    STORE_CETTIRE,
)
from models.product import Product
from scanner.base_scanner import BaseScanner
from utils.parser import (
    extract_json_ld_blocks,
    extract_text,
    filter_json_ld_by_type,
    get_attr,
    normalize_url,
    parse_html,
    parse_price,
    safe_dict_get,
)

logger = logging.getLogger(__name__)


class CettireScanner(BaseScanner):
    """Scanner implementation for Cettire."""

    PRODUCT_SELECTORS = [
        "div.product-card",
        "li.product-item",
        "article[data-product]",
        "div.grid-product",
    ]
    NAME_SELECTORS = [
        ".product-card__title",
        ".product-name",
        "h2 a",
        "h3 a",
        "[data-product-title]",
    ]
    BRAND_SELECTORS = [
        ".product-card__brand",
        ".product-brand",
        "[data-product-brand]",
    ]
    PRICE_SELECTORS = [
        ".product-card__price",
        ".price",
        "[data-product-price]",
    ]
    SALE_PRICE_SELECTORS = [
        ".sale-price",
        ".product-card__sale-price",
        "[data-sale-price]",
    ]
    ORIGINAL_PRICE_SELECTORS = [
        ".original-price",
        ".product-card__original-price",
        "s.price",
        "[data-original-price]",
    ]
    LINK_SELECTORS = ["a.product-card__link", "a[href*='/products/']", "h2 a", "h3 a"]
    IMAGE_SELECTORS = ["img.product-card__image", "img[data-src]", "img[src]"]
    SKU_SELECTORS = ["[data-product-sku]", "[data-sku]", ".product-sku"]

    @property
    def store_name(self) -> str:
        return STORE_CETTIRE

    @property
    def country(self) -> str:
        return COUNTRY_US

    @property
    def base_url(self) -> str:
        return CETTIRE_BASE_URL

    @property
    def default_currency(self) -> str:
        return CURRENCY_USD

    def build_search_url(self, query: str) -> str:
        """
        Build a Cettire search URL for the given query.

        Args:
            query: Search keywords.

        Returns:
            Absolute search URL.
        """
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
        """
        Parse product listings from an HTML document string.

        JSON-LD Product blocks are preferred; HTML cards are used as fallback.

        Args:
            html: Raw HTML content.
            limit: Maximum number of products to return.

        Returns:
            Deduplicated list of Product instances.
        """
        soup = parse_html(html)
        products = self._parse_json_ld_products(soup)
        html_products = self._parse_html_products(soup, limit=limit)

        if not products:
            products = html_products
        else:
            products = self._merge_products(products, html_products)

        deduplicated = self._deduplicate_products(products)
        result = deduplicated[:limit]
        logger.debug("Cettire parsed %d products from HTML", len(result))
        return result

    def _parse_json_ld_products(self, soup: BeautifulSoup) -> list[Product]:
        blocks = extract_json_ld_blocks(soup)
        product_blocks = filter_json_ld_by_type(blocks, "Product")
        products: list[Product] = []

        for block in product_blocks:
            product = self._parse_json_ld_product(block)
            if product is not None:
                products.append(product)

        return products

    def _parse_json_ld_product(self, block: dict[str, Any]) -> Product | None:
        name = str(block.get("name", "")).strip()
        brand_data = block.get("brand")
        brand = self._extract_brand_name(brand_data)
        sku = str(block.get("sku") or block.get("productID") or "").strip()
        image = block.get("image")
        image_url = self._extract_image_url(image)
        offers = block.get("offers")
        price_info = self._extract_offer_prices(offers)
        url = normalize_url(self.base_url, price_info.get("url", ""))
        in_stock = self._parse_availability(price_info.get("availability", ""))

        return self._make_product(
            name=name,
            brand=brand,
            price=price_info.get("price"),
            currency=price_info.get("currency") or self.default_currency,
            url=url,
            image_url=normalize_url(self.base_url, image_url),
            sku=sku,
            in_stock=in_stock,
            original_price=price_info.get("original_price"),
            sale_price=price_info.get("sale_price"),
        )

    def _parse_html_products(self, soup: BeautifulSoup, limit: int) -> list[Product]:
        cards = self._find_product_cards(soup)
        products: list[Product] = []

        for card in cards:
            if len(products) >= limit:
                break
            product = self._parse_card(card)
            if product is not None:
                products.append(product)

        return products

    def _find_product_cards(self, soup: BeautifulSoup) -> list[Tag]:
        for selector in self.PRODUCT_SELECTORS:
            cards = soup.select(selector)
            if cards:
                return cards
        return soup.select("a[href*='/products/']")

    def _parse_card(self, card: Tag) -> Product | None:
        name = self._extract_from_selectors(card, self.NAME_SELECTORS)
        brand = self._extract_from_selectors(card, self.BRAND_SELECTORS) or "Unknown"
        sale_text = self._extract_from_selectors(card, self.SALE_PRICE_SELECTORS)
        original_text = self._extract_from_selectors(card, self.ORIGINAL_PRICE_SELECTORS)
        price_text = self._extract_from_selectors(card, self.PRICE_SELECTORS)

        sale_price = parse_price(sale_text)
        original_price = parse_price(original_text)
        price = parse_price(price_text)

        link_el = self._first_element(card, self.LINK_SELECTORS)
        href = get_attr(link_el, "href")
        url = normalize_url(self.base_url, href)

        if not name and link_el is not None:
            name = extract_text(link_el)

        image_el = self._first_element(card, self.IMAGE_SELECTORS)
        image_url = get_attr(image_el, "data-src") or get_attr(image_el, "src")
        image_url = normalize_url(self.base_url, image_url)

        sku = self._extract_sku(card)

        return self._make_product(
            name=name,
            brand=brand,
            price=price,
            currency=self.default_currency,
            url=url,
            image_url=image_url,
            sku=sku,
            original_price=original_price,
            sale_price=sale_price,
        )

    def _merge_products(
        self,
        primary: list[Product],
        secondary: list[Product],
    ) -> list[Product]:
        seen_urls = {item.url.strip().lower() for item in primary if item.url}
        seen_skus = {item.sku.strip().lower() for item in primary if item.sku}
        merged = list(primary)

        for product in secondary:
            url_key = product.url.strip().lower()
            sku_key = product.sku.strip().lower()
            if url_key and url_key in seen_urls:
                continue
            if sku_key and sku_key in seen_skus:
                continue
            merged.append(product)
            if url_key:
                seen_urls.add(url_key)
            if sku_key:
                seen_skus.add(sku_key)

        return merged

    def _extract_sku(self, card: Tag) -> str:
        for selector in self.SKU_SELECTORS:
            element = card.select_one(selector)
            if element is None:
                continue
            text = extract_text(element)
            if text:
                return text
            for attr in ("data-product-sku", "data-sku"):
                value = get_attr(element, attr)
                if value:
                    return value
        return ""

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

    @staticmethod
    def _extract_brand_name(brand_data: Any) -> str:
        if isinstance(brand_data, dict):
            return str(brand_data.get("name", "")).strip()
        if isinstance(brand_data, str):
            return brand_data.strip()
        return ""

    @staticmethod
    def _extract_image_url(image_data: Any) -> str:
        if isinstance(image_data, list) and image_data:
            return str(image_data[0])
        if isinstance(image_data, str):
            return image_data
        return ""

    @staticmethod
    def _extract_offer_prices(offers: Any) -> dict[str, Any]:
        if isinstance(offers, list) and offers:
            offers = offers[0]
        if not isinstance(offers, dict):
            return {}

        price = safe_dict_get(offers, "price")
        parsed_price = parse_price(str(price)) if price is not None else None
        currency = str(offers.get("priceCurrency") or "").strip() or None
        url = str(offers.get("url") or "").strip()
        availability = str(offers.get("availability") or "").strip()

        return {
            "price": parsed_price,
            "currency": currency,
            "url": url,
            "availability": availability,
            "original_price": None,
            "sale_price": None,
        }

    @staticmethod
    def _parse_availability(availability: str) -> bool:
        lowered = availability.lower()
        if "outofstock" in lowered or "soldout" in lowered:
            return False
        if "instock" in lowered or "preorder" in lowered:
            return True
        return True
