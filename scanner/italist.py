"""
Italist store scanner.
"""

import logging
from typing import Any
from urllib.parse import quote_plus

from bs4 import BeautifulSoup, Tag

from config.constants import (
    COUNTRY_IT,
    CURRENCY_EUR,
    DEFAULT_SCAN_LIMIT,
    ITALIST_BASE_URL,
    STORE_ITALIST,
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


class ItalistScanner(BaseScanner):
    """Scanner implementation for Italist."""

    PRODUCT_SELECTORS = [
        "div.product-tile",
        "li.product-grid-item",
        "article.product-card",
        "div.product-item",
    ]
    NAME_SELECTORS = [
        ".product-tile__title",
        ".product-name",
        "h2.product-title",
        "a.product-link",
        ".product-card__title",
    ]
    BRAND_SELECTORS = [
        ".product-tile__brand",
        ".product-brand",
        ".product-vendor",
        "[data-product-brand]",
    ]
    PRICE_SELECTORS = [
        ".product-tile__price",
        ".price",
        ".product-price",
        "[data-product-price]",
    ]
    SALE_PRICE_SELECTORS = [
        ".product-tile__sale-price",
        ".sale-price",
        ".price--sale",
        "[data-sale-price]",
    ]
    ORIGINAL_PRICE_SELECTORS = [
        ".product-tile__original-price",
        ".original-price",
        "s.price",
        "[data-original-price]",
    ]
    LINK_SELECTORS = [
        "a.product-tile__link",
        "a.product-link",
        "a[href*='/products/']",
    ]
    IMAGE_SELECTORS = [
        "img.product-tile__image",
        "img.product-image",
        "img[src]",
        "img[data-src]",
    ]
    SKU_SELECTORS = [
        "[data-product-sku]",
        "[data-sku]",
        ".product-sku",
    ]

    @property
    def store_name(self) -> str:
        return STORE_ITALIST

    @property
    def country(self) -> str:
        return COUNTRY_IT

    @property
    def base_url(self) -> str:
        return ITALIST_BASE_URL

    @property
    def default_currency(self) -> str:
        return CURRENCY_EUR

    def build_search_url(self, query: str) -> str:
        """
        Build an Italist search URL for the given query.

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

        JSON-LD ItemList and Product blocks are preferred; HTML cards are fallback.

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
        logger.debug("Italist parsed %d products from HTML", len(result))
        return result

    def _parse_json_ld_products(self, soup: BeautifulSoup) -> list[Product]:
        blocks = extract_json_ld_blocks(soup)
        products: list[Product] = []
        seen_keys: set[str] = set()

        for item_list in filter_json_ld_by_type(blocks, "ItemList"):
            for product in self._parse_item_list(item_list):
                key = self._product_key(product)
                if key and key in seen_keys:
                    continue
                if key:
                    seen_keys.add(key)
                products.append(product)

        for block in filter_json_ld_by_type(blocks, "Product"):
            product = self._parse_json_ld_product(block)
            if product is None:
                continue
            key = self._product_key(product)
            if key and key in seen_keys:
                continue
            if key:
                seen_keys.add(key)
            products.append(product)

        return products

    def _parse_item_list(self, item_list: dict[str, Any]) -> list[Product]:
        elements = item_list.get("itemListElement", [])
        if not isinstance(elements, list):
            elements = [elements]

        products: list[Product] = []
        for element in elements:
            if not isinstance(element, dict):
                continue
            item = element.get("item", element)
            if not isinstance(item, dict):
                continue
            if not self._looks_like_product(item):
                continue
            product = self._parse_json_ld_product(item)
            if product is not None:
                products.append(product)

        return products

    def _parse_json_ld_product(self, block: dict[str, Any]) -> Product | None:
        name = str(block.get("name", "")).strip()
        brand = self._extract_brand_name(block.get("brand"))
        sku = str(block.get("sku") or block.get("productID") or "").strip()
        image_url = self._extract_image_url(block.get("image"))
        price_info = self._extract_offer_prices(block.get("offers"))
        url = normalize_url(self.base_url, price_info.get("url", "") or block.get("url", ""))
        in_stock = self._parse_availability(price_info.get("availability", ""))

        original_price = price_info.get("original_price")
        sale_price = price_info.get("sale_price")
        price = price_info.get("price")
        original_price, sale_price, effective_price = self._normalize_prices(
            original_price, sale_price, price, name=name
        )
        if effective_price is None:
            logger.warning(
                "Skipping Italist JSON-LD product with unparseable price (name=%r, sku=%r)",
                name,
                sku,
            )
            return None

        return self._make_product(
            name=name,
            brand=brand,
            price=effective_price,
            currency=price_info.get("currency") or self.default_currency,
            url=url,
            image_url=normalize_url(self.base_url, image_url),
            sku=sku,
            in_stock=in_stock,
            original_price=original_price,
            sale_price=sale_price,
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
        brand = self._extract_from_selectors(card, self.BRAND_SELECTORS)
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
        original_price, sale_price, effective_price = self._normalize_prices(
            original_price, sale_price, price, name=name
        )
        if effective_price is None:
            logger.warning(
                "Skipping Italist HTML product with unparseable price (name=%r, sku=%r)",
                name,
                sku,
            )
            return None

        return self._make_product(
            name=name,
            brand=brand,
            price=effective_price,
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

    def _normalize_prices(
        self,
        original_price: float | None,
        sale_price: float | None,
        price: float | None,
        name: str = "",
    ) -> tuple[float | None, float | None, float | None]:
        """
        Normalize regular and sale prices into consistent values.

        Args:
            original_price: Regular list price.
            sale_price: Discounted sale price.
            price: Generic price when regular/sale are absent.
            name: Product name for logging.

        Returns:
            Tuple of (original_price, sale_price, effective_price).
        """
        if (
            sale_price is not None
            and original_price is not None
            and sale_price > original_price
        ):
            logger.warning(
                "Italist sale price exceeds original price for %r; values swapped",
                name or "unknown product",
            )
            sale_price, original_price = original_price, sale_price

        if sale_price is not None:
            effective_price = sale_price
        elif original_price is not None:
            effective_price = original_price
        else:
            effective_price = price

        return original_price, sale_price, effective_price

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
    def _looks_like_product(item: dict[str, Any]) -> bool:
        item_type = item.get("@type", "")
        if isinstance(item_type, list):
            return "Product" in item_type
        if item_type == "Product":
            return True
        return bool(item.get("name"))

    @staticmethod
    def _product_key(product: Product) -> str:
        if product.url.strip():
            return product.url.strip().lower()
        if product.sku.strip():
            return product.sku.strip().lower()
        return product.name.strip().lower()

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

    def _extract_offer_prices(self, offers: Any) -> dict[str, Any]:
        if isinstance(offers, list):
            parsed_offers = [
                self._parse_single_offer(offer)
                for offer in offers
                if isinstance(offer, dict)
            ]
            in_stock_offers = [
                offer
                for offer in parsed_offers
                if offer.get("price") is not None
                and self._parse_availability(str(offer.get("availability", "")))
            ]
            if in_stock_offers:
                return in_stock_offers[0]

            for offer in parsed_offers:
                if offer.get("price") is not None:
                    return offer
            return {}

        if isinstance(offers, dict):
            return self._parse_single_offer(offers)

        return {}

    @staticmethod
    def _parse_single_offer(offer: dict[str, Any]) -> dict[str, Any]:
        price = safe_dict_get(offer, "price")
        parsed_price = parse_price(str(price)) if price is not None else None
        currency = str(offer.get("priceCurrency") or "").strip() or None
        url = str(offer.get("url") or "").strip()
        availability = str(offer.get("availability") or "").strip()

        high_price = offer.get("highPrice") or offer.get("listPrice")
        parsed_original = parse_price(str(high_price)) if high_price is not None else None

        sale_price = parsed_price if parsed_original and parsed_price else None
        if parsed_original and parsed_price and parsed_price >= parsed_original:
            sale_price = None

        return {
            "price": parsed_price,
            "currency": currency,
            "url": url,
            "availability": availability,
            "original_price": parsed_original,
            "sale_price": sale_price,
        }

    @staticmethod
    def _parse_availability(availability: str) -> bool:
        lowered = availability.lower()
        if "outofstock" in lowered or "soldout" in lowered or "discontinued" in lowered:
            return False
        if "instock" in lowered or "preorder" in lowered or "limitedavailability" in lowered:
            return True
        return True
