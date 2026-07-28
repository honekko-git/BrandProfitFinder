"""
Excel column definitions and templates.
"""

from typing import Final

PRODUCT_COLUMNS: Final[list[str]] = [
    "name",
    "brand",
    "model",
    "sku",
    "category",
    "gender",
    "price",
    "currency",
    "shipping_cost",
    "tax_cost",
    "fee_cost",
    "exchange_rate",
    "landed_cost",
    "rakuten_price",
    "yahoo_price",
    "mercari_price",
    "ebay_price",
    "profit",
    "roi",
    "margin",
    "store_name",
    "country",
    "url",
    "image_url",
    "in_stock",
    "scraped_at",
    "last_updated",
]

RANKING_COLUMNS: Final[list[str]] = ["rank", "label", "score"]
