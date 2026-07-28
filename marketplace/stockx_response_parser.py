"""
StockX internal standard response parser.

Parses BrandProfitFinder internal StockX fixture JSON (not an official API format).
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any

from config.constants import CURRENCY_JPY, MARKETPLACE_STOCKX
from marketplace.amazon_price_normalizer import parse_jpy_price
from marketplace.stockx_exceptions import StockXParseError, StockXResponseError
from models.marketplace_listing import MarketplaceListing
from used_luxury.condition_normalizer import ConditionNormalizer
from used_luxury.enrichment import UsedItemEnricher

logger = logging.getLogger(__name__)

_JAN_PATTERN = re.compile(r"^\d{8,13}$")
_NEW_CONDITIONS = frozenset(
    {
        "new",
        "deadstock",
        "new with box",
        "new without box",
        "new with defects",
        "display item",
    }
)
_PREOWNED_CONDITIONS = frozenset(
    {"pre-owned", "pre owned", "used", "refurbished", "damaged", "for parts"}
)


class StockXSaleStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SOLD = "SOLD"
    INACTIVE = "INACTIVE"
    REMOVED = "REMOVED"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_value(cls, value: Any) -> "StockXSaleStatus":
        if value is None:
            return cls.UNKNOWN
        text = str(value).strip().upper().replace("-", "_").replace(" ", "_")
        try:
            return cls(text)
        except ValueError:
            return cls.UNKNOWN


class StockXInventoryStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    LOW_SUPPLY = "LOW_SUPPLY"
    SOLD_OUT = "SOLD_OUT"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_value(cls, value: Any) -> "StockXInventoryStatus":
        if value is None:
            return cls.UNKNOWN
        text = str(value).strip().upper().replace("-", "_").replace(" ", "_")
        try:
            return cls(text)
        except ValueError:
            return cls.UNKNOWN


@dataclass
class StockXParseResult:
    listings: list[MarketplaceListing] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rejected_count: int = 0
    valid_count: int = 0


class StockXResponseParser:
    """Parse internal standard StockX JSON into marketplace listings."""

    def __init__(
        self,
        condition_normalizer: ConditionNormalizer | None = None,
        enricher: UsedItemEnricher | None = None,
    ) -> None:
        self._condition_normalizer = condition_normalizer or ConditionNormalizer()
        self._enricher = enricher or UsedItemEnricher()

    def parse(
        self,
        payload: dict[str, object],
        *,
        source_query: str = "",
        include_unavailable: bool = False,
        include_sold: bool = False,
        include_inactive: bool = False,
        include_new: bool = True,
        include_preowned: bool = False,
        include_low_liquidity: bool = True,
        require_known_lowest_ask: bool = True,
        require_known_shipping: bool = False,
        require_known_fees: bool = False,
        minimum_sales_last_30_days: int = 0,
        minimum_asks_count: int = 0,
        minimum_bids_count: int = 0,
        maximum_volatility_rate: float | None = None,
        preferred_price_source: str = "LOWEST_ASK",
        allow_unknown_currency: bool = False,
        default_currency: str = CURRENCY_JPY,
    ) -> StockXParseResult:
        """Parse StockX internal standard JSON into listings."""
        result = StockXParseResult()
        items = payload.get("items")
        if items is None:
            return result
        if not isinstance(items, list):
            raise StockXParseError("StockX items must be a list when present")

        price_source_pref = StockXSettings_normalize_price_source(preferred_price_source)
        seen_ids: set[str] = set()

        for item in items:
            if not isinstance(item, dict):
                result.rejected_count += 1
                result.warnings.append("skipped non-object item")
                continue

            listing_id = str(item.get("listing_id") or "").strip()
            if not listing_id:
                result.rejected_count += 1
                result.warnings.append("skipped item without listing_id")
                continue
            if listing_id in seen_ids:
                result.warnings.append(f"skipped duplicate listing_id: {listing_id}")
                result.rejected_count += 1
                continue

            sale_status = StockXSaleStatus.from_value(item.get("sale_status"))
            inventory_status = _parse_inventory_status(item.get("inventory"))
            inventory_quantity = _parse_inventory_quantity(item.get("inventory"))
            item_warnings = _inventory_sale_warnings(
                sale_status, inventory_status, inventory_quantity, item.get("market")
            )

            if not _should_include_sale_inventory(
                sale_status,
                inventory_status,
                include_sold=include_sold,
                include_inactive=include_inactive,
                include_unavailable=include_unavailable,
            ):
                result.rejected_count += 1
                continue

            condition_raw, condition_key, condition_warnings = _resolve_condition(
                item.get("condition"),
                normalizer=self._condition_normalizer,
            )
            item_warnings.extend(condition_warnings)

            if not include_new and condition_key in _NEW_CONDITIONS:
                result.rejected_count += 1
                continue
            if not include_preowned and condition_key in _PREOWNED_CONDITIONS:
                result.rejected_count += 1
                continue

            market_meta = _parse_market_block(item.get("market"), default_currency=default_currency)
            item_warnings.extend(market_meta.pop("warnings", []))

            if not include_low_liquidity and _is_low_liquidity(market_meta):
                result.rejected_count += 1
                continue

            if minimum_sales_last_30_days > 0:
                sales_30 = market_meta.get("sales_last_30_days")
                if sales_30 is None or sales_30 < minimum_sales_last_30_days:
                    result.rejected_count += 1
                    continue

            if minimum_asks_count > 0:
                asks = market_meta.get("asks_count")
                if asks is None or asks < minimum_asks_count:
                    result.rejected_count += 1
                    continue

            if minimum_bids_count > 0:
                bids = market_meta.get("bids_count")
                if bids is None or bids < minimum_bids_count:
                    result.rejected_count += 1
                    continue

            if maximum_volatility_rate is not None:
                vol = market_meta.get("volatility_rate")
                if vol is not None and vol > maximum_volatility_rate:
                    result.rejected_count += 1
                    continue

            if require_known_lowest_ask and market_meta.get("lowest_ask_known") is not True:
                if price_source_pref == "LOWEST_ASK":
                    result.rejected_count += 1
                    continue

            listing, parse_warnings = self._parse_item(
                item,
                source_query=source_query,
                sale_status=sale_status,
                inventory_status=inventory_status,
                inventory_quantity=inventory_quantity,
                market_meta=market_meta,
                condition_raw=condition_raw,
                condition_key=condition_key,
                preferred_price_source=price_source_pref,
                allow_unknown_currency=allow_unknown_currency,
                default_currency=default_currency,
                extra_warnings=item_warnings,
            )
            if listing is None:
                result.rejected_count += 1
                result.warnings.extend(parse_warnings)
                continue

            if require_known_shipping and listing.shipping_unknown:
                result.rejected_count += 1
                continue

            fees_known = listing.source_metadata.get("source_stockx_fees_known")
            if require_known_fees and fees_known is not True:
                result.rejected_count += 1
                continue

            seen_ids.add(listing_id)
            result.listings.append(listing)
            result.warnings.extend(parse_warnings)

        result.valid_count = len(result.listings)
        return result

    def parse_metadata(self, payload: dict[str, object]) -> dict[str, Any]:
        total = payload.get("total")
        page = payload.get("page")
        page_size = payload.get("page_size")
        parsed_page = page if isinstance(page, int) and page >= 1 else None
        parsed_total = total if isinstance(total, int) and total >= 0 else None
        parsed_page_size = page_size if isinstance(page_size, int) and page_size >= 1 else None
        items = payload.get("items")
        item_count = len(items) if isinstance(items, list) else 0
        has_next = item_count > 0 and parsed_page is not None
        return {
            "total": parsed_total,
            "page": parsed_page,
            "page_size": parsed_page_size,
            "item_count": item_count,
            "has_next_page": has_next,
            "next_page": str(parsed_page + 1) if has_next and parsed_page else None,
        }

    def _parse_item(
        self,
        item: dict[str, Any],
        *,
        source_query: str,
        sale_status: StockXSaleStatus,
        inventory_status: StockXInventoryStatus,
        inventory_quantity: int | None,
        market_meta: dict[str, Any],
        condition_raw: str,
        condition_key: str,
        preferred_price_source: str,
        allow_unknown_currency: bool,
        default_currency: str,
        extra_warnings: list[str],
    ) -> tuple[MarketplaceListing | None, list[str]]:
        warnings: list[str] = list(extra_warnings)
        listing_id = str(item.get("listing_id") or "").strip()
        title = str(item.get("title") or "").strip()
        if not title:
            warnings.append(f"skipped item without title (listing_id={listing_id})")
            return None, warnings

        price_jpy, currency, price_source, price_warnings = _resolve_listing_price(
            item.get("price"),
            market_meta=market_meta,
            preferred_price_source=preferred_price_source,
            default_currency=default_currency,
            allow_unknown_currency=allow_unknown_currency,
        )
        warnings.extend(price_warnings)
        if price_jpy is None:
            warnings.append(f"skipped item without valid price (listing_id={listing_id})")
            return None, warnings

        shipping_jpy, shipping_unknown, ship_warnings = _parse_money_block(
            item.get("shipping"), block_name="shipping"
        )
        warnings.extend(ship_warnings)

        fees_meta = _parse_fees_block(item.get("fees"))
        warnings.extend(fees_meta.pop("warnings", []))

        auth_meta = _parse_authentication_block(item.get("authentication"))
        warnings.extend(auth_meta.pop("warnings", []))

        listing_url = str(item.get("url") or "").strip()
        image_url = str(item.get("image_url") or "").strip()
        model_number = str(item.get("model_number") or "").strip()
        style_code = str(item.get("style_code") or "").strip()
        brand = str(item.get("brand") or "").strip()
        color = str(item.get("color") or "").strip()
        size = str(item.get("size") or "").strip() if item.get("size") is not None else ""
        size_system = str(item.get("size_system") or "").strip() or None

        sku_raw = str(item.get("sku") or "").strip()
        jan_raw = item.get("jan")
        jan_code = str(jan_raw).strip() if jan_raw is not None else ""
        if jan_code and not _JAN_PATTERN.match(jan_code):
            warnings.append("invalid JAN format; stored in metadata only")
            jan_code = ""

        release_year = _parse_release_year(item.get("release_year"))
        if item.get("release_year") is not None and release_year is None:
            warnings.append("invalid release_year")
        release_date = _parse_release_date(item.get("release_date"))
        if item.get("release_date") is not None and release_date is None:
            warnings.append("invalid release_date")

        used_details = None
        if condition_key in _PREOWNED_CONDITIONS:
            enrich_input = dict(item)
            if isinstance(item.get("condition"), dict):
                enrich_input["condition"] = {
                    **item["condition"],
                    "raw": condition_raw,
                }
            used_details = self._enricher.enrich(
                enrich_input,
                price_jpy=price_jpy,
                shipping_unknown=shipping_unknown,
                listing_url=listing_url,
                image_url=image_url,
                model_number=model_number,
            )
            warnings.extend(used_details.warnings)

        source_metadata: dict[str, Any] = {
            "source_marketplace": MARKETPLACE_STOCKX,
            "source_listing_id": listing_id,
            "source_currency": currency,
            "source_size": size or None,
            "source_size_system": size_system,
            "source_jan": str(jan_raw).strip() if jan_raw is not None else None,
            "source_category": str(item.get("category") or "").strip() or None,
            "source_sub_category": str(item.get("sub_category") or "").strip() or None,
            "source_gender": str(item.get("gender") or "").strip() or None,
            "source_shipping_known": not shipping_unknown,
            "source_sale_status": sale_status.value,
            "source_inventory_status": inventory_status.value,
            "source_inventory_quantity": inventory_quantity,
            "source_listed_at": str(item.get("listed_at") or "").strip() or None,
            "source_stockx_product_id": str(item.get("product_id") or "").strip() or None,
            "source_stockx_variant_id": str(item.get("variant_id") or "").strip() or None,
            "source_stockx_style_code": style_code or None,
            "source_style_code": style_code or None,
            "source_stockx_sku": sku_raw or None,
            "source_stockx_size_system": size_system,
            "source_stockx_release_year": release_year,
            "source_stockx_release_date": release_date,
            "source_stockx_price_source": price_source,
            "source_stockx_lowest_ask": market_meta.get("lowest_ask"),
            "source_stockx_lowest_ask_currency": market_meta.get("lowest_ask_currency"),
            "source_stockx_lowest_ask_known": market_meta.get("lowest_ask_known"),
            "source_stockx_highest_bid": market_meta.get("highest_bid"),
            "source_stockx_highest_bid_currency": market_meta.get("highest_bid_currency"),
            "source_stockx_highest_bid_known": market_meta.get("highest_bid_known"),
            "source_stockx_last_sale": market_meta.get("last_sale"),
            "source_stockx_last_sale_currency": market_meta.get("last_sale_currency"),
            "source_stockx_last_sale_known": market_meta.get("last_sale_known"),
            "source_stockx_sales_72h": market_meta.get("sales_last_72_hours"),
            "source_stockx_sales_30d": market_meta.get("sales_last_30_days"),
            "source_stockx_asks_count": market_meta.get("asks_count"),
            "source_stockx_bids_count": market_meta.get("bids_count"),
            "source_stockx_premium_rate": market_meta.get("price_premium_rate"),
            "source_stockx_volatility_rate": market_meta.get("volatility_rate"),
            "source_stockx_fees_known": fees_meta.get("fees_known"),
            "source_stockx_fees_amount": fees_meta.get("fees_amount"),
            "source_stockx_fees_currency": fees_meta.get("fees_currency"),
            "source_stockx_fees_currency": fees_meta.get("fees_currency"),
            "authentication_status": auth_meta.get("authentication_status"),
            "stockx_parse_warnings": None,
        }

        listing = MarketplaceListing(
            marketplace_name=MARKETPLACE_STOCKX,
            listing_id=listing_id,
            title=title,
            brand=brand,
            model_number=model_number,
            sku="",
            jan_code=jan_code,
            condition=condition_raw,
            price_jpy=price_jpy,
            shipping_jpy=shipping_jpy,
            shipping_unknown=shipping_unknown,
            seller_name="",
            seller_rating=None,
            listing_url=listing_url,
            image_url=image_url,
            availability=_availability_from_status(sale_status, inventory_status),
            source_query=source_query,
            currency=currency,
            used_item_details=used_details,
            source_metadata=source_metadata,
        )
        listing.source_metadata["stockx_parse_warnings"] = "; ".join(warnings) if warnings else None
        return listing, warnings

    @staticmethod
    def validate_payload(payload: dict[str, object]) -> None:
        if not isinstance(payload, dict):
            raise StockXResponseError("StockX payload must be a JSON object")
        items = payload.get("items")
        if items is not None and not isinstance(items, list):
            raise StockXResponseError("StockX items must be a list when present")


def StockXSettings_normalize_price_source(value: str) -> str:
    from marketplace.stockx_settings import StockXSettings

    return StockXSettings.normalize_price_source(value)


def preprocess_stockx_condition(raw: str | None) -> tuple[str, str, list[str]]:
    """Preprocess StockX condition strings; returns (normalized_key, display, warnings)."""
    warnings: list[str] = []
    if raw is None or not str(raw).strip():
        return "unknown", "unknown", warnings

    text = unicodedata.normalize("NFKC", str(raw).strip().lower())
    text = re.sub(r"\s+", " ", text)

    mappings: tuple[tuple[str, str, str | None], ...] = (
        (r"^deadstock$", "deadstock", "deadstock does not assert perfect unworn condition"),
        (r"^new with box$", "new with box", "new with box describes packaging; box condition separate"),
        (r"^new without box$", "new without box", "new without box does not assert pre-owned status"),
        (r"^new with defects$", "new with defects", "new with defects indicates known defects"),
        (r"^display item$", "display item", "display item may have show-floor wear"),
        (r"^pre[- ]?owned$", "pre-owned", None),
        (r"^used$", "used", None),
        (r"^refurbished$", "refurbished", "refurbished is not treated as new"),
        (r"^damaged$", "damaged", "damaged condition treated conservatively"),
        (r"^for parts$", "for parts", "for parts is lowest usable condition tier"),
        (r"^new$", "new", "new does not assert unopened guarantee"),
        (r"^unknown$", "unknown", None),
        (r"^記載なし$", "unknown", None),
    )
    for pattern, key, warn in mappings:
        if re.search(pattern, text):
            if warn:
                warnings.append(warn)
            return key, key, warnings

    return text, text, warnings


def _resolve_condition(
    block: Any,
    *,
    normalizer: ConditionNormalizer,
) -> tuple[str, str, list[str]]:
    raw = ""
    if isinstance(block, dict):
        raw = str(block.get("raw") or "").strip()
    elif isinstance(block, str):
        raw = block.strip()

    condition_key, display, warnings = preprocess_stockx_condition(raw)

    if condition_key in _PREOWNED_CONDITIONS:
        normalized = normalizer.normalize(condition_key)
        warnings.extend(normalized.warnings)
        return normalized.normalized_condition.value.lower(), condition_key, warnings

    if condition_key in _NEW_CONDITIONS or condition_key in {"new", "unknown"}:
        normalized = normalizer.normalize(condition_key if condition_key != "unknown" else "unknown")
        warnings.extend(normalized.warnings)
        return normalized.normalized_condition.value.lower(), condition_key, warnings

    return display or "unknown", condition_key, warnings


def _parse_market_block(block: Any, *, default_currency: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "lowest_ask": None,
        "lowest_ask_currency": default_currency,
        "lowest_ask_known": False,
        "highest_bid": None,
        "highest_bid_currency": default_currency,
        "highest_bid_known": False,
        "last_sale": None,
        "last_sale_currency": default_currency,
        "last_sale_known": False,
        "sales_last_72_hours": None,
        "sales_last_30_days": None,
        "asks_count": None,
        "bids_count": None,
        "price_premium_rate": None,
        "volatility_rate": None,
        "warnings": [],
    }
    if not isinstance(block, dict):
        return result

    for key, prefix in (
        ("lowest_ask", "lowest_ask"),
        ("highest_bid", "highest_bid"),
        ("last_sale", "last_sale"),
    ):
        parsed = _parse_market_price(block.get(key), default_currency=default_currency)
        result[f"{prefix}"] = parsed.get("amount")
        result[f"{prefix}_currency"] = parsed.get("currency")
        result[f"{prefix}_known"] = parsed.get("known")
        result["warnings"].extend(parsed.get("warnings", []))

    for count_key in ("sales_last_72_hours", "sales_last_30_days", "asks_count", "bids_count"):
        value = block.get(count_key)
        if value is None:
            continue
        if isinstance(value, bool):
            result["warnings"].append(f"invalid bool for {count_key}")
            continue
        if isinstance(value, int) and value >= 0:
            result[count_key] = value
        elif isinstance(value, float) and value.is_integer() and value >= 0:
            result[count_key] = int(value)
        else:
            result["warnings"].append(f"invalid {count_key}")

    for rate_key in ("price_premium_rate", "volatility_rate"):
        value = block.get(rate_key)
        if value is None:
            continue
        if isinstance(value, bool):
            result["warnings"].append(f"invalid bool for {rate_key}")
            continue
        try:
            rate = float(value)
            if rate < 0:
                result["warnings"].append(f"negative {rate_key} rejected")
                continue
            if rate_key == "price_premium_rate" and rate > 10:
                result["warnings"].append("price_premium_rate unusually high; verify decimal format")
            result[rate_key] = rate
        except (TypeError, ValueError):
            result["warnings"].append(f"invalid {rate_key}")

    return result


def _parse_market_price(block: Any, *, default_currency: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "amount": None,
        "currency": default_currency.upper(),
        "known": False,
        "warnings": [],
    }
    if not isinstance(block, dict):
        return result
    known = block.get("known")
    if known is False:
        result["known"] = False
        return result
    if known is True:
        result["known"] = True
    amount = block.get("amount")
    if amount is None:
        result["known"] = False if known is None else result["known"]
        return result
    if isinstance(amount, bool):
        result["warnings"].append("invalid bool market price amount")
        return result
    try:
        value = float(amount)
        if value < 0:
            result["warnings"].append("negative market price rejected")
            return result
        result["amount"] = parse_jpy_price(Decimal(str(value))) if value == int(value) else Decimal(str(value))
        if isinstance(block.get("currency"), str) and block["currency"].strip():
            result["currency"] = block["currency"].strip().upper()
        result["known"] = True if known is not False else result["known"]
    except (TypeError, ValueError):
        result["warnings"].append("invalid market price amount")
    return result


def _resolve_listing_price(
    price_block: Any,
    *,
    market_meta: dict[str, Any],
    preferred_price_source: str,
    default_currency: str,
    allow_unknown_currency: bool,
) -> tuple[Decimal | None, str, str, list[str]]:
    warnings: list[str] = []
    item_price, currency, item_source, item_warnings = _parse_item_price_block(
        price_block,
        default_currency=default_currency,
        allow_unknown_currency=allow_unknown_currency,
    )
    warnings.extend(item_warnings)

    if preferred_price_source == "LOWEST_ASK":
        if market_meta.get("lowest_ask_known") is True and market_meta.get("lowest_ask") is not None:
            return (
                market_meta["lowest_ask"],
                market_meta.get("lowest_ask_currency") or currency,
                "LOWEST_ASK",
                warnings,
            )
        if item_price is not None and item_source == "LOWEST_ASK":
            return item_price, currency, "LOWEST_ASK", warnings
        if item_price is not None:
            warnings.append("preferred LOWEST_ASK unavailable; using item price")
            return item_price, currency, item_source or "LISTING_PRICE", warnings
        return None, currency, "UNKNOWN", warnings

    if preferred_price_source == "LAST_SALE":
        if market_meta.get("last_sale_known") is True and market_meta.get("last_sale") is not None:
            warnings.append("last sale is historical reference price only")
            return (
                market_meta["last_sale"],
                market_meta.get("last_sale_currency") or currency,
                "LAST_SALE",
                warnings,
            )
        if item_price is not None:
            warnings.append("last sale unavailable; using item price as reference")
            return item_price, currency, item_source or "LISTING_PRICE", warnings
        return None, currency, "UNKNOWN", warnings

    if item_price is not None:
        return item_price, currency, item_source or "LISTING_PRICE", warnings
    return None, currency, "UNKNOWN", warnings


def _parse_item_price_block(
    block: Any,
    *,
    default_currency: str,
    allow_unknown_currency: bool,
) -> tuple[Decimal | None, str, str, list[str]]:
    warnings: list[str] = []
    currency = default_currency.upper()
    source = "UNKNOWN"
    if not isinstance(block, dict):
        return None, currency, source, warnings

    if isinstance(block.get("currency"), str) and block["currency"].strip():
        currency = block["currency"].strip().upper()

    source_raw = block.get("source")
    if source_raw is not None:
        source = str(source_raw).strip().upper().replace("-", "_").replace(" ", "_")

    amount = block.get("amount")
    if amount is None or isinstance(amount, bool):
        if amount is not None:
            warnings.append("invalid bool price amount")
        return None, currency, source, warnings

    try:
        value = float(amount)
        if value < 0:
            warnings.append("negative price rejected")
            return None, currency, source, warnings
        if currency != CURRENCY_JPY and not allow_unknown_currency:
            warnings.append(f"non-JPY currency {currency} excluded")
            return None, currency, source, warnings
        price = parse_jpy_price(Decimal(str(int(value)))) if value == int(value) else Decimal(str(value))
        return price, currency, source, warnings
    except (TypeError, ValueError):
        warnings.append("invalid price amount")
        return None, currency, source, warnings


def _parse_money_block(block: Any, *, block_name: str) -> tuple[Decimal | None, bool, list[str]]:
    warnings: list[str] = []
    if not isinstance(block, dict):
        return None, True, warnings
    known = block.get("known")
    if known is False:
        return None, True, warnings
    amount = block.get("amount")
    if amount is None:
        return None, known is not True, warnings
    if isinstance(amount, bool):
        warnings.append(f"invalid bool {block_name} amount")
        return None, True, warnings
    try:
        value = float(amount)
        if value < 0:
            warnings.append(f"negative {block_name} amount rejected")
            return None, True, warnings
        return Decimal(str(int(value))) if value == int(value) else Decimal(str(value)), False, warnings
    except (TypeError, ValueError):
        warnings.append(f"invalid {block_name} amount")
        return None, True, warnings


def _parse_fees_block(block: Any) -> dict[str, Any]:
    amount, unknown, warnings = _parse_money_block(block, block_name="fees")
    currency = CURRENCY_JPY
    known = False if block is None else not unknown
    if isinstance(block, dict) and isinstance(block.get("currency"), str):
        currency = block["currency"].strip().upper()
    if isinstance(block, dict) and block.get("known") is False:
        known = False
    elif isinstance(block, dict) and block.get("known") is True and amount is not None:
        known = True
    return {
        "fees_amount": amount,
        "fees_currency": currency,
        "fees_known": known,
        "warnings": warnings,
    }


def _parse_authentication_block(block: Any) -> dict[str, Any]:
    warnings: list[str] = []
    status = "UNKNOWN"
    if not isinstance(block, dict):
        return {"authentication_status": status, "warnings": warnings}

    status_raw = block.get("status")
    if status_raw is not None:
        status = str(status_raw).strip().upper().replace("-", "_").replace(" ", "_")

    seller_claimed = block.get("seller_claimed_authentic")
    platform_auth = block.get("platform_authenticated")
    if seller_claimed is True and platform_auth is False:
        warnings.append("seller claimed authentic but platform authentication is false")
    if status == "PLATFORM_PROCESS" and platform_auth is True:
        warnings.append("platform process status does not assert completed authentication")
    if platform_auth is None and status.endswith("AUTHENTICATED"):
        warnings.append("authentication status wording does not assert platform verification")

    return {"authentication_status": status, "warnings": warnings}


def _parse_inventory_status(block: Any) -> StockXInventoryStatus:
    if isinstance(block, dict):
        return StockXInventoryStatus.from_value(block.get("status"))
    return StockXInventoryStatus.UNKNOWN


def _parse_inventory_quantity(block: Any) -> int | None:
    if not isinstance(block, dict):
        return None
    quantity = block.get("quantity")
    if quantity is None:
        return None
    if isinstance(quantity, bool):
        return None
    if isinstance(quantity, int) and quantity >= 0:
        return quantity
    return None


def _parse_release_year(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        year = int(value)
        if 1900 <= year <= 2100:
            return year
    except (TypeError, ValueError):
        pass
    return None


def _parse_release_date(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        return text
    return None


def _should_include_sale_inventory(
    sale_status: StockXSaleStatus,
    inventory_status: StockXInventoryStatus,
    *,
    include_sold: bool,
    include_inactive: bool,
    include_unavailable: bool,
) -> bool:
    if sale_status == StockXSaleStatus.SOLD and not include_sold:
        return False
    if sale_status in {StockXSaleStatus.INACTIVE, StockXSaleStatus.REMOVED} and not include_inactive:
        return False
    if inventory_status in {StockXInventoryStatus.UNAVAILABLE, StockXInventoryStatus.SOLD_OUT}:
        return include_unavailable
    return True


def _inventory_sale_warnings(
    sale_status: StockXSaleStatus,
    inventory_status: StockXInventoryStatus,
    quantity: int | None,
    market_block: Any,
) -> list[str]:
    warnings: list[str] = []
    if sale_status == StockXSaleStatus.ACTIVE and inventory_status == StockXInventoryStatus.SOLD_OUT:
        warnings.append("sale_status ACTIVE conflicts with SOLD_OUT inventory")
    if inventory_status == StockXInventoryStatus.AVAILABLE and quantity == 0:
        warnings.append("AVAILABLE inventory with quantity 0")
    if isinstance(market_block, dict):
        asks = market_block.get("asks_count")
        if asks == 0 and inventory_status == StockXInventoryStatus.AVAILABLE:
            warnings.append("asks_count 0 with AVAILABLE inventory")
    return warnings


def _is_low_liquidity(market_meta: dict[str, Any]) -> bool:
    sales_30 = market_meta.get("sales_last_30_days")
    asks = market_meta.get("asks_count")
    if sales_30 is not None and sales_30 < 5:
        return True
    if asks is not None and asks < 3:
        return True
    return False


def _availability_from_status(
    sale_status: StockXSaleStatus,
    inventory_status: StockXInventoryStatus,
) -> str:
    if sale_status == StockXSaleStatus.SOLD or inventory_status == StockXInventoryStatus.SOLD_OUT:
        return "sold"
    if sale_status in {StockXSaleStatus.INACTIVE, StockXSaleStatus.REMOVED}:
        return "ended"
    if inventory_status in {StockXInventoryStatus.AVAILABLE, StockXInventoryStatus.LOW_SUPPLY}:
        return "in_stock"
    if inventory_status == StockXInventoryStatus.UNAVAILABLE:
        return "out_of_stock"
    return "unknown"
