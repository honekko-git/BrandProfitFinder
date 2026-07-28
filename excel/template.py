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
    "original_price",
    "sale_price",
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

PRICE_RESULT_COLUMNS: Final[list[str]] = [
    "store_name",
    "brand",
    "name",
    "sku",
    "url",
    "image_url",
    "currency",
    "original_price",
    "sale_price",
    "source_purchase_price",
    "exchange_rate",
    "purchase_price_jpy",
    "international_shipping_jpy",
    "customs_duty_jpy",
    "import_tax_jpy",
    "domestic_shipping_jpy",
    "marketplace_fee_jpy",
    "other_costs_jpy",
    "total_cost_jpy",
    "domestic_market",
    "domestic_sale_price_jpy",
    "profit_jpy",
    "profit_margin",
    "roi",
    "is_profitable",
    "ranking_score",
    "calculation_status",
    "error_message",
]

RANKING_COLUMNS: Final[list[str]] = ["rank", "label", "score"]

NUMERIC_PRICE_RESULT_COLUMNS: Final[frozenset[str]] = frozenset(
    {
        "original_price",
        "sale_price",
        "source_purchase_price",
        "exchange_rate",
        "purchase_price_jpy",
        "international_shipping_jpy",
        "customs_duty_jpy",
        "import_tax_jpy",
        "domestic_shipping_jpy",
        "marketplace_fee_jpy",
        "other_costs_jpy",
        "total_cost_jpy",
        "domestic_sale_price_jpy",
        "profit_jpy",
        "profit_margin",
        "roi",
        "ranking_score",
    }
)

URL_COLUMNS: Final[frozenset[str]] = frozenset({"url", "image_url", "listing_url"})

MARKETPLACE_LISTING_COLUMNS: Final[list[str]] = [
    "marketplace_name",
    "listing_id",
    "title",
    "brand",
    "model_number",
    "sku",
    "jan_code",
    "condition",
    "price_jpy",
    "shipping_jpy",
    "total_price_jpy",
    "seller_name",
    "seller_rating",
    "listing_url",
    "image_url",
    "availability",
    "sold_count",
    "source_query",
    "matched_product_id",
    "match_score",
    "is_valid",
    "validation_error",
]
