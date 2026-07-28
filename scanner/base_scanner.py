"""
Base scanner interface for overseas stores.

Every store scanner must inherit this class and return Product objects.
Network access and site-specific scraping are implemented in later phases.
"""

import logging
from abc import ABC, abstractmethod

from config.constants import DEFAULT_SCAN_LIMIT
from models.product import Product
from utils.validator import validate_scraped_product

logger = logging.getLogger(__name__)


class BaseScanner(ABC):
    """Abstract base class for overseas store scanners."""

    @property
    @abstractmethod
    def store_name(self) -> str:
        """Return the display name of the store."""

    @property
    @abstractmethod
    def country(self) -> str:
        """Return the store country code."""

    @abstractmethod
    def scan(self, query: str, limit: int = DEFAULT_SCAN_LIMIT) -> list[Product]:
        """
        Collect products for the given query.

        Args:
            query: Search keywords.
            limit: Maximum number of products to return.

        Returns:
            List of Product instances. Must not return dict or tuple.
        """

    def create_product(
        self,
        name: str,
        brand: str,
        price: float,
        currency: str,
        url: str = "",
        image_url: str = "",
        sku: str = "",
        in_stock: bool = True,
        original_price: float | None = None,
        sale_price: float | None = None,
    ) -> Product:
        """
        Create a Product with store metadata applied.

        Args:
            name: Product name.
            brand: Brand name.
            price: Listed price.
            currency: Price currency code.
            url: Product page URL.
            image_url: Product image URL.
            sku: Optional SKU.
            in_stock: Stock availability flag.
            original_price: Regular price before discount.
            sale_price: Discounted sale price.

        Returns:
            Product instance bound to this scanner's store metadata.
        """
        return Product(
            name=name,
            brand=brand,
            price=price,
            original_price=original_price,
            sale_price=sale_price,
            currency=currency,
            store_name=self.store_name,
            country=self.country,
            url=url,
            image_url=image_url,
            sku=sku,
            in_stock=in_stock,
        )

    def _make_product(
        self,
        name: str,
        brand: str,
        price: float | None = None,
        currency: str | None = None,
        url: str = "",
        image_url: str = "",
        sku: str = "",
        in_stock: bool = True,
        original_price: float | None = None,
        sale_price: float | None = None,
    ) -> Product | None:
        """
        Build a validated Product or skip invalid scraped data.

        Args:
            name: Product name.
            brand: Brand name.
            price: Effective listed price.
            currency: ISO currency code.
            url: Product page URL.
            image_url: Product image URL.
            sku: Product identifier.
            in_stock: Stock availability flag.
            original_price: Regular list price.
            sale_price: Discounted sale price.

        Returns:
            Product instance or None when validation fails.
        """
        effective_price = self._resolve_effective_price(price, original_price, sale_price)
        effective_currency = currency or getattr(self, "default_currency", "USD")

        is_valid, reason = validate_scraped_product(
            name=name,
            brand=brand,
            price=effective_price,
            url=url,
            sku=sku,
        )
        if not is_valid:
            logger.warning(
                "Skipping invalid product from %s: %s (name=%r, url=%r, sku=%r)",
                self.store_name,
                reason,
                name,
                url,
                sku,
            )
            return None

        return self.create_product(
            name=name.strip(),
            brand=brand.strip() if brand else "Unknown",
            price=effective_price if effective_price is not None else 0.0,
            currency=effective_currency,
            url=url,
            image_url=image_url,
            sku=sku.strip() if sku else "",
            in_stock=in_stock,
            original_price=original_price,
            sale_price=sale_price,
        )

    def _deduplicate_products(self, products: list[Product]) -> list[Product]:
        """
        Remove duplicate products by URL or SKU.

        Args:
            products: Parsed product list.

        Returns:
            Deduplicated product list preserving first occurrence order.
        """
        seen_urls: set[str] = set()
        seen_skus: set[str] = set()
        unique: list[Product] = []

        for product in products:
            url_key = product.url.strip().lower()
            sku_key = product.sku.strip().lower()

            if url_key and url_key in seen_urls:
                logger.debug("Skipping duplicate URL in %s: %s", self.store_name, product.url)
                continue
            if sku_key and sku_key in seen_skus:
                logger.debug("Skipping duplicate SKU in %s: %s", self.store_name, product.sku)
                continue

            if url_key:
                seen_urls.add(url_key)
            if sku_key:
                seen_skus.add(sku_key)
            unique.append(product)

        return unique

    @staticmethod
    def _resolve_effective_price(
        price: float | None,
        original_price: float | None,
        sale_price: float | None,
    ) -> float | None:
        """
        Choose the effective listed price from available price fields.

        Args:
            price: Explicit price value.
            original_price: Regular list price.
            sale_price: Discounted sale price.

        Returns:
            Resolved price or None.
        """
        if price is not None:
            return price
        if sale_price is not None:
            return sale_price
        return original_price
