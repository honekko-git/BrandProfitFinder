"""
Farfetch internal standard response parser.

Parses BrandProfitFinder internal Farfetch fixture JSON (not an official API format).
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any

from config.constants import CURRENCY_JPY, MARKETPLACE_FARFETCH
from marketplace.amazon_price_normalizer import parse_jpy_price
from marketplace.farfetch_exceptions import FarfetchParseError, FarfetchResponseError
from models.marketplace_listing import MarketplaceListing
from used_luxury.condition_normalizer import ConditionNormalizer

logger = logging.getLogger(__name__)

_JAN_PATTERN = re.compile(r"^\d{8,13}$")


class FarfetchSaleStatus(str, Enum):
    """Listing sale status."""

    ACTIVE = "ACTIVE"
    RESERVED = "RESERVED"
    SOLD = "SOLD"
    INACTIVE = "INACTIVE"
    REMOVED = "REMOVED"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_value(cls, value: Any) -> "FarfetchSaleStatus":
        if value is None:
            return cls.UNKNOWN
        text = str(value).strip().upper().replace("-", "_").replace(" ", "_")
        try:
            return cls(text)
        except ValueError:
            return cls.UNKNOWN


class FarfetchInventoryStatus(str, Enum):
    """Inventory availability."""

    IN_STOCK = "IN_STOCK"
    LOW_STOCK = "LOW_STOCK"
    RESERVED = "RESERVED"
    SOLD = "SOLD"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_value(cls, value: Any) -> "FarfetchInventoryStatus":
        if value is None:
            return cls.UNKNOWN
        text = str(value).strip().upper().replace("-", "_").replace(" ", "_")
        try:
            return cls(text)
        except ValueError:
            return cls.UNKNOWN


class FarfetchBoutiqueType(str, Enum):
    """Boutique source category."""

    PARTNER_BOUTIQUE = "PARTNER_BOUTIQUE"
    PLATFORM_INVENTORY = "PLATFORM_INVENTORY"
    BRAND_BOUTIQUE = "BRAND_BOUTIQUE"
    DEPARTMENT_STORE = "DEPARTMENT_STORE"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_value(cls, value: Any) -> "FarfetchBoutiqueType":
        if value is None:
            return cls.UNKNOWN
        text = str(value).strip().upper().replace("-", "_").replace(" ", "_")
        try:
            return cls(text)
        except ValueError:
            return cls.UNKNOWN


@dataclass
class FarfetchParseResult:
    """Result of parsing a Farfetch search payload."""

    listings: list[MarketplaceListing] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rejected_count: int = 0
    valid_count: int = 0


class FarfetchResponseParser:
    """Parse internal standard Farfetch JSON into marketplace listings."""

    def __init__(self, condition_normalizer: ConditionNormalizer | None = None) -> None:
        self._condition_normalizer = condition_normalizer or ConditionNormalizer()

    def parse(
        self,
        payload: dict[str, object],
        *,
        source_query: str = "",
        include_sold: bool = False,
        include_reserved: bool = False,
        include_unavailable: bool = False,
        include_discounted_only: bool = False,
        include_full_price_only: bool = False,
        include_low_stock: bool = True,
        include_final_sale: bool = False,
        include_partner_boutiques: bool = True,
        include_platform_inventory: bool = True,
        require_known_shipping: bool = False,
        require_known_duties: bool = False,
        allow_unknown_currency: bool = False,
        default_currency: str = CURRENCY_JPY,
        filter_warnings: list[str] | None = None,
    ) -> FarfetchParseResult:
        """Parse Farfetch internal standard JSON into listings."""
        result = FarfetchParseResult()
        if filter_warnings:
            result.warnings.extend(filter_warnings)

        items = payload.get("items")
        if items is None:
            return result
        if not isinstance(items, list):
            raise FarfetchParseError("Farfetch items must be a list when present")

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

            sale_status = FarfetchSaleStatus.from_value(item.get("sale_status"))
            inventory_status = _parse_inventory_status(item.get("inventory"))
            inventory_quantity = _parse_inventory_quantity(item.get("inventory"))
            low_stock = _parse_low_stock(item.get("inventory"))
            filter_warnings_item = _inventory_sale_warnings(sale_status, inventory_status, inventory_quantity)

            if not _should_include_item(
                sale_status,
                inventory_status,
                include_sold=include_sold,
                include_reserved=include_reserved,
                include_unavailable=include_unavailable,
            ):
                result.rejected_count += 1
                continue

            if not include_low_stock and low_stock is True:
                result.rejected_count += 1
                continue

            discount_meta = _parse_discount_block(item.get("discount"))
            if include_discounted_only and not discount_meta.get("discount_active"):
                result.rejected_count += 1
                continue
            if include_full_price_only and discount_meta.get("discount_active"):
                result.rejected_count += 1
                continue

            boutique_meta = _parse_boutique_block(item.get("boutique"))
            filter_warnings_item.extend(boutique_meta.get("warnings", []))
            if not _should_include_boutique(
                boutique_meta.get("boutique_type"),
                include_partner_boutiques=include_partner_boutiques,
                include_platform_inventory=include_platform_inventory,
            ):
                result.rejected_count += 1
                continue

            return_meta = _parse_return_policy_block(item.get("return_policy"))
            filter_warnings_item.extend(return_meta.get("warnings", []))
            if not include_final_sale and return_meta.get("final_sale") is True:
                result.rejected_count += 1
                continue

            variant_meta = _parse_variants_block(item.get("variants"), item.get("variant_id"))
            filter_warnings_item.extend(variant_meta.get("warnings", []))
            if variant_meta.get("all_unavailable"):
                filter_warnings_item.append("all variants unavailable")

            listing, item_warnings = self._parse_item(
                item,
                source_query=source_query,
                allow_unknown_currency=allow_unknown_currency,
                default_currency=default_currency,
                sale_status=sale_status,
                inventory_status=inventory_status,
                inventory_quantity=inventory_quantity,
                low_stock=low_stock,
                discount_meta=discount_meta,
                boutique_meta=boutique_meta,
                return_meta=return_meta,
                variant_meta=variant_meta,
                extra_warnings=filter_warnings_item,
            )
            if listing is None:
                result.rejected_count += 1
                result.warnings.extend(item_warnings)
                continue

            if require_known_shipping and listing.shipping_unknown:
                result.rejected_count += 1
                continue

            duties_known = listing.source_metadata.get("source_duties_known")
            if require_known_duties and duties_known is not True:
                result.rejected_count += 1
                continue

            seen_ids.add(listing_id)
            result.listings.append(listing)
            result.warnings.extend(item_warnings)

        result.valid_count = len(result.listings)
        return result

    def parse_metadata(self, payload: dict[str, object]) -> dict[str, Any]:
        """Extract pagination metadata from payload."""
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
        allow_unknown_currency: bool,
        default_currency: str,
        sale_status: FarfetchSaleStatus,
        inventory_status: FarfetchInventoryStatus,
        inventory_quantity: int | None,
        low_stock: bool | None,
        discount_meta: dict[str, Any],
        boutique_meta: dict[str, Any],
        return_meta: dict[str, Any],
        variant_meta: dict[str, Any],
        extra_warnings: list[str],
    ) -> tuple[MarketplaceListing | None, list[str]]:
        warnings: list[str] = list(extra_warnings)
        listing_id = str(item.get("listing_id") or "").strip()
        title = str(item.get("title") or "").strip()
        if not title:
            warnings.append(f"skipped item without title (listing_id={listing_id})")
            return None, warnings

        price_jpy, currency, price_warnings = _parse_price_block(
            item.get("price"),
            default_currency=default_currency,
            allow_unknown_currency=allow_unknown_currency,
        )
        warnings.extend(price_warnings)
        if price_jpy is None:
            warnings.append(f"skipped item without valid price (listing_id={listing_id})")
            return None, warnings

        shipping_jpy, shipping_unknown, ship_warnings = _parse_shipping_block(item.get("shipping"))
        warnings.extend(ship_warnings)

        duties_meta = _parse_duties_block(item.get("duties"))
        warnings.extend(duties_meta.pop("warnings", []))

        original_price_meta = _parse_original_price_block(
            item.get("original_price"),
            default_currency=default_currency,
            allow_unknown_currency=allow_unknown_currency,
            current_price=price_jpy,
        )
        warnings.extend(original_price_meta.pop("warnings", []))

        if discount_meta.get("discount_inconsistent"):
            warnings.append("discount amount and rate are inconsistent")

        listing_url = str(item.get("url") or "").strip()
        image_url = str(item.get("image_url") or "").strip()
        model_number = str(item.get("model_number") or "").strip()
        style_code = str(item.get("style_code") or "").strip()
        brand = str(item.get("brand") or "").strip()
        designer = str(item.get("designer") or "").strip()
        color = str(item.get("color") or "").strip()
        size = str(item.get("size") or "").strip() if item.get("size") is not None else ""

        jan_raw = item.get("jan")
        jan_code = str(jan_raw).strip() if jan_raw is not None else ""
        if jan_code and not _JAN_PATTERN.match(jan_code):
            warnings.append("invalid JAN format; stored in metadata only")
            jan_code = ""

        condition_raw, condition_warnings = _resolve_condition(
            item.get("condition"),
            normalizer=self._condition_normalizer,
        )
        warnings.extend(condition_warnings)

        source_metadata: dict[str, Any] = {
            "source_marketplace": MARKETPLACE_FARFETCH,
            "source_listing_id": listing_id,
            "source_currency": currency,
            "source_product_id": str(item.get("product_id") or "").strip() or None,
            "source_variant_id": str(item.get("variant_id") or "").strip() or None,
            "source_designer": designer or None,
            "source_style_code": style_code or None,
            "source_jan": str(jan_raw).strip() if jan_raw is not None else None,
            "source_category": str(item.get("category") or "").strip() or None,
            "source_sub_category": str(item.get("sub_category") or "").strip() or None,
            "source_material": str(item.get("material") or "").strip() or None,
            "source_gender": str(item.get("gender") or "").strip() or None,
            "source_season": str(item.get("season") or "").strip() or None,
            "source_collection": str(item.get("collection") or "").strip() or None,
            "source_shipping_known": not shipping_unknown,
            "source_duties_included": duties_meta.get("duties_included"),
            "source_duties_known": duties_meta.get("duties_known"),
            "source_duties_amount": duties_meta.get("duties_amount"),
            "source_duties_currency": duties_meta.get("duties_currency"),
            "source_sale_status": sale_status.value,
            "source_original_price": original_price_meta.get("original_price"),
            "source_discount_active": discount_meta.get("discount_active"),
            "source_discount_amount": discount_meta.get("discount_amount"),
            "source_discount_rate": discount_meta.get("discount_rate"),
            "source_previous_price": discount_meta.get("previous_price"),
            "source_inventory_status": inventory_status.value,
            "source_inventory_quantity": inventory_quantity,
            "source_low_stock": low_stock,
            "source_boutique_type": boutique_meta.get("boutique_type"),
            "source_boutique_country": boutique_meta.get("boutique_country"),
            "source_boutique_verified": boutique_meta.get("boutique_verified"),
            "source_return_accepted": return_meta.get("return_accepted"),
            "source_return_period_days": return_meta.get("return_period_days"),
            "source_final_sale": return_meta.get("final_sale"),
            "source_listed_at": str(item.get("listed_at") or "").strip() or None,
            "source_variant_count": variant_meta.get("variant_count"),
            "source_available_variant_count": variant_meta.get("available_variant_count"),
            "source_selected_variant_id": variant_meta.get("selected_variant_id"),
            "source_selected_variant_sku": variant_meta.get("selected_variant_sku"),
            "farfetch_parse_warnings": None,
        }

        availability = _availability_from_status(sale_status, inventory_status)

        listing = MarketplaceListing(
            marketplace_name=MARKETPLACE_FARFETCH,
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
            availability=availability,
            source_query=source_query,
            currency=currency,
            used_item_details=None,
            source_metadata=source_metadata,
        )
        all_warnings = warnings
        listing.source_metadata["farfetch_parse_warnings"] = "; ".join(all_warnings) if all_warnings else None
        return listing, all_warnings

    @staticmethod
    def validate_payload(payload: dict[str, object]) -> None:
        """Validate top-level payload structure."""
        if not isinstance(payload, dict):
            raise FarfetchResponseError("Farfetch payload must be a JSON object")
        items = payload.get("items")
        if items is not None and not isinstance(items, list):
            raise FarfetchResponseError("Farfetch items must be a list when present")


def _resolve_condition(
    block: Any,
    *,
    normalizer: ConditionNormalizer,
) -> tuple[str, list[str]]:
    warnings: list[str] = []
    raw = ""
    if isinstance(block, dict):
        raw = str(block.get("raw") or "").strip()
    elif isinstance(block, str):
        raw = block.strip()

    preprocessed, cond_warnings = preprocess_farfetch_condition(raw)
    warnings.extend(cond_warnings)

    if preprocessed in {"pre-owned", "pre owned", "refurbished"}:
        normalized = normalizer.normalize(preprocessed)
        warnings.extend(normalized.warnings)
        return normalized.normalized_condition.value.lower(), warnings

    if preprocessed in {"new", "like new", "excellent", "very good", "good", "fair", "poor", "unknown"}:
        normalized = normalizer.normalize(preprocessed)
        warnings.extend(normalized.warnings)
        return normalized.normalized_condition.value.lower(), warnings

    return preprocessed or "unknown", warnings


def _parse_variants_block(block: Any, selected_variant_id: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "variant_count": 0,
        "available_variant_count": 0,
        "selected_variant_id": None,
        "selected_variant_sku": None,
        "all_unavailable": False,
        "warnings": [],
    }
    if block is None:
        return result
    if not isinstance(block, list):
        result["warnings"].append("variants must be a list when present")
        return result

    selected_id = str(selected_variant_id or "").strip()
    available_count = 0
    for entry in block:
        if not isinstance(entry, dict):
            result["warnings"].append("skipped non-object variant")
            continue
        result["variant_count"] += 1
        available = entry.get("available")
        if available is True:
            available_count += 1
        qty = entry.get("quantity")
        if qty is not None and (isinstance(qty, bool) or not isinstance(qty, int) or qty < 0):
            result["warnings"].append("invalid variant quantity")
        price_block = entry.get("price")
        if isinstance(price_block, dict):
            amount = price_block.get("amount")
            if isinstance(amount, bool):
                result["warnings"].append("boolean variant price rejected")
            elif amount is not None and parse_jpy_price(amount) is None:
                result["warnings"].append("invalid variant price")
        variant_id = str(entry.get("variant_id") or "").strip()
        if selected_id and variant_id == selected_id:
            result["selected_variant_id"] = variant_id
            sku = str(entry.get("sku") or "").strip()
            result["selected_variant_sku"] = sku or None

    result["available_variant_count"] = available_count
    if result["variant_count"] > 0 and available_count == 0:
        result["all_unavailable"] = True
    return result


def _parse_boutique_block(block: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "boutique_type": FarfetchBoutiqueType.UNKNOWN.value,
        "boutique_country": None,
        "boutique_verified": None,
        "warnings": [],
    }
    if not isinstance(block, dict):
        return result

    boutique_type = FarfetchBoutiqueType.from_value(block.get("type"))
    result["boutique_type"] = boutique_type.value

    country = block.get("country")
    if country is not None:
        result["boutique_country"] = str(country).strip().upper() or None

    verified = block.get("verified")
    if isinstance(verified, bool):
        result["boutique_verified"] = verified
    elif verified is not None:
        result["warnings"].append("boutique verified must be boolean or unknown")

    return result


def _should_include_boutique(
    boutique_type: str | None,
    *,
    include_partner_boutiques: bool,
    include_platform_inventory: bool,
) -> bool:
    if boutique_type == FarfetchBoutiqueType.PARTNER_BOUTIQUE.value and not include_partner_boutiques:
        return False
    if boutique_type == FarfetchBoutiqueType.PLATFORM_INVENTORY.value and not include_platform_inventory:
        return False
    return True


def _parse_return_policy_block(block: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "return_accepted": None,
        "return_period_days": None,
        "final_sale": None,
        "warnings": [],
    }
    if not isinstance(block, dict):
        return result

    accepted = block.get("accepted")
    if isinstance(accepted, bool):
        result["return_accepted"] = accepted
    elif accepted is not None:
        result["warnings"].append("return accepted must be boolean or unknown")

    period = block.get("period_days")
    if period is None:
        pass
    elif isinstance(period, bool):
        result["warnings"].append("boolean return period_days rejected")
    elif isinstance(period, int) and period >= 0:
        result["return_period_days"] = period
    else:
        result["warnings"].append("invalid return period_days")

    final_sale = block.get("final_sale")
    if isinstance(final_sale, bool):
        result["final_sale"] = final_sale
    elif final_sale is not None:
        result["warnings"].append("final_sale must be boolean or unknown")

    if result["final_sale"] is True and result["return_accepted"] is True:
        result["warnings"].append("final_sale=true conflicts with return accepted=true")

    return result


def _parse_duties_block(block: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "duties_included": None,
        "duties_known": False,
        "duties_amount": None,
        "duties_currency": None,
        "warnings": [],
    }
    if block is None:
        return result
    if not isinstance(block, dict):
        result["warnings"].append("invalid duties block")
        return result

    if block.get("known") is False:
        return result

    result["duties_known"] = True
    included = block.get("included")
    if isinstance(included, bool):
        result["duties_included"] = included
    elif included is not None:
        result["warnings"].append("duties included must be boolean or unknown")

    amount_raw = block.get("amount")
    if amount_raw is None:
        return result

    if isinstance(amount_raw, bool):
        result["warnings"].append("boolean duties amount rejected")
        return result

    amount = parse_jpy_price(amount_raw)
    if amount is None:
        result["warnings"].append("invalid duties amount")
        return result

    result["duties_amount"] = float(amount)
    currency = block.get("currency")
    if currency is not None:
        result["duties_currency"] = str(currency).strip().upper() or None
    return result


def _parse_low_stock(block: Any) -> bool | None:
    if not isinstance(block, dict):
        return None
    raw = block.get("low_stock")
    if isinstance(raw, bool):
        return raw
    return None


def _should_include_item(
    sale_status: FarfetchSaleStatus,
    inventory_status: FarfetchInventoryStatus,
    *,
    include_sold: bool,
    include_reserved: bool,
    include_unavailable: bool,
) -> bool:
    if sale_status == FarfetchSaleStatus.SOLD and not include_sold:
        return False
    if sale_status == FarfetchSaleStatus.RESERVED and not include_reserved:
        return False
    if sale_status in {FarfetchSaleStatus.INACTIVE, FarfetchSaleStatus.REMOVED} and not include_unavailable:
        return False
    if inventory_status == FarfetchInventoryStatus.SOLD and not include_sold:
        return False
    if inventory_status == FarfetchInventoryStatus.RESERVED and not include_reserved:
        return False
    if inventory_status == FarfetchInventoryStatus.UNAVAILABLE and not include_unavailable:
        return False
    if sale_status in {FarfetchSaleStatus.ACTIVE, FarfetchSaleStatus.UNKNOWN} and inventory_status in {
        FarfetchInventoryStatus.IN_STOCK,
        FarfetchInventoryStatus.LOW_STOCK,
        FarfetchInventoryStatus.UNKNOWN,
    }:
        return True
    if include_sold and (sale_status == FarfetchSaleStatus.SOLD or inventory_status == FarfetchInventoryStatus.SOLD):
        return True
    if include_reserved and (
        sale_status == FarfetchSaleStatus.RESERVED or inventory_status == FarfetchInventoryStatus.RESERVED
    ):
        return True
    if include_unavailable and (
        sale_status in {FarfetchSaleStatus.INACTIVE, FarfetchSaleStatus.REMOVED}
        or inventory_status == FarfetchInventoryStatus.UNAVAILABLE
    ):
        return True
    return False


def _inventory_sale_warnings(
    sale_status: FarfetchSaleStatus,
    inventory_status: FarfetchInventoryStatus,
    quantity: int | None,
) -> list[str]:
    warnings: list[str] = []
    if sale_status == FarfetchSaleStatus.ACTIVE and inventory_status in {
        FarfetchInventoryStatus.SOLD,
        FarfetchInventoryStatus.UNAVAILABLE,
    }:
        warnings.append(
            f"sale_status {sale_status.value} conflicts with inventory {inventory_status.value}"
        )
    if inventory_status == FarfetchInventoryStatus.IN_STOCK and quantity == 0:
        warnings.append("quantity 0 conflicts with IN_STOCK inventory status")
    return warnings


def _parse_inventory_status(block: Any) -> FarfetchInventoryStatus:
    if not isinstance(block, dict):
        return FarfetchInventoryStatus.UNKNOWN
    return FarfetchInventoryStatus.from_value(block.get("status"))


def _parse_inventory_quantity(block: Any) -> int | None:
    if not isinstance(block, dict):
        return None
    raw = block.get("quantity")
    if raw is None or isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        return None
    return raw


def _parse_price_block(
    block: Any,
    *,
    default_currency: str,
    allow_unknown_currency: bool,
) -> tuple[Decimal | None, str, list[str]]:
    warnings: list[str] = []
    if not isinstance(block, dict):
        return None, default_currency, ["missing price block"]

    amount_raw = block.get("amount")
    if isinstance(amount_raw, bool):
        return None, default_currency, ["boolean price rejected"]

    currency = str(block.get("currency") or default_currency).strip().upper() or default_currency
    amount = parse_jpy_price(amount_raw)
    if amount is None:
        return None, currency, ["invalid price amount"]

    if currency != CURRENCY_JPY:
        msg = f"unsupported currency {currency}; no conversion applied"
        warnings.append(msg)
        if not allow_unknown_currency:
            return None, currency, warnings

    return amount, currency, warnings


def _parse_shipping_block(block: Any) -> tuple[Decimal | None, bool, list[str]]:
    warnings: list[str] = []
    if block is None:
        return None, True, []
    if not isinstance(block, dict):
        return None, True, ["invalid shipping block"]

    if block.get("known") is False:
        return None, True, []

    amount_raw = block.get("amount")
    if amount_raw is None:
        return None, True, []

    if isinstance(amount_raw, bool):
        return None, True, ["boolean shipping amount rejected"]

    if amount_raw == 0 or amount_raw == 0.0:
        return Decimal("0"), False, warnings

    amount = parse_jpy_price(amount_raw)
    if amount is None:
        return None, True, ["invalid shipping amount"]
    return amount, False, warnings


def _parse_original_price_block(
    block: Any,
    *,
    default_currency: str,
    allow_unknown_currency: bool,
    current_price: Decimal,
) -> dict[str, Any]:
    warnings: list[str] = []
    if block is None or not isinstance(block, dict):
        if block is not None and not isinstance(block, dict):
            warnings.append("invalid original_price block")
        return {"original_price": None, "warnings": warnings}

    if block.get("known") is False:
        return {"original_price": None, "warnings": warnings}

    amount_raw = block.get("amount")
    if amount_raw is None:
        return {"original_price": None, "warnings": warnings}

    if isinstance(amount_raw, bool):
        warnings.append("boolean original_price rejected")
        return {"original_price": None, "warnings": warnings}

    currency = str(block.get("currency") or default_currency).strip().upper() or default_currency
    amount = parse_jpy_price(amount_raw)
    if amount is None:
        warnings.append("invalid original_price amount")
        return {"original_price": None, "warnings": warnings}

    if currency != CURRENCY_JPY and not allow_unknown_currency:
        warnings.append(f"unsupported original_price currency {currency}")
        return {"original_price": None, "warnings": warnings}

    if amount < current_price:
        warnings.append("original_price is below current price")

    return {"original_price": float(amount), "warnings": warnings}


def _parse_discount_block(block: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "discount_active": False,
        "discount_amount": None,
        "discount_rate": None,
        "previous_price": None,
    }
    if not isinstance(block, dict):
        return result

    result["discount_active"] = block.get("active") is True

    amount_raw = block.get("amount")
    if amount_raw is not None and not isinstance(amount_raw, bool):
        amount = parse_jpy_price(amount_raw)
        if amount is not None and amount >= 0:
            result["discount_amount"] = float(amount)

    rate_raw = block.get("rate")
    if rate_raw is not None and not isinstance(rate_raw, bool):
        try:
            rate = float(rate_raw)
            if 0 <= rate <= 1:
                result["discount_rate"] = rate
        except (TypeError, ValueError):
            pass

    previous_raw = block.get("previous_price")
    if previous_raw is not None and not isinstance(previous_raw, bool):
        previous = parse_jpy_price(previous_raw)
        if previous is not None:
            result["previous_price"] = float(previous)

    if (
        result["discount_amount"] is not None
        and result["previous_price"] is not None
        and result["discount_rate"] is not None
        and float(result["previous_price"]) > 0
    ):
        implied_rate = float(result["discount_amount"]) / float(result["previous_price"])
        if abs(implied_rate - float(result["discount_rate"])) > 0.05:
            result["discount_inconsistent"] = True

    return result


def _availability_from_status(
    sale_status: FarfetchSaleStatus,
    inventory_status: FarfetchInventoryStatus,
) -> str:
    if sale_status == FarfetchSaleStatus.SOLD or inventory_status == FarfetchInventoryStatus.SOLD:
        return "sold"
    if sale_status == FarfetchSaleStatus.RESERVED or inventory_status == FarfetchInventoryStatus.RESERVED:
        return "reserved"
    if inventory_status == FarfetchInventoryStatus.UNAVAILABLE:
        return "unavailable"
    if sale_status in {FarfetchSaleStatus.INACTIVE, FarfetchSaleStatus.REMOVED}:
        return "ended"
    if inventory_status in {FarfetchInventoryStatus.IN_STOCK, FarfetchInventoryStatus.LOW_STOCK}:
        return "in_stock"
    return "unknown"


def preprocess_farfetch_condition(raw: str | None) -> tuple[str, list[str]]:
    """
    Preprocess Farfetch condition strings before normalization.

    Does not treat New Season as condition grade or conflate tags with condition.
    """
    warnings: list[str] = []
    if raw is None or not str(raw).strip():
        return "", warnings

    text = unicodedata.normalize("NFKC", str(raw).strip().lower())
    text = re.sub(r"\s+", " ", text)

    mappings = (
        (r"^new season$", "new season"),
        (r"^new with tags$", "new with tags"),
        (r"^new without tags$", "new without tags"),
        (r"^display item$", "display item"),
        (r"^shop worn$", "shop worn"),
        (r"^pre[- ]?owned$", "pre-owned"),
        (r"^refurbished$", "refurbished"),
        (r"^new$", "new"),
        (r"^記載なし$", ""),
    )
    for pattern, replacement in mappings:
        if re.search(pattern, text):
            if replacement == "new season":
                warnings.append("new season indicates collection timing, not condition grade")
            if replacement == "new with tags":
                warnings.append("new with tags describes tags; not conflated with accessories")
            if replacement == "new without tags":
                warnings.append("new without tags does not assert pre-owned status")
            if replacement == "display item":
                warnings.append("display item may have show-floor wear")
            if replacement == "shop worn":
                warnings.append("shop worn may indicate try-on or display wear")
            if replacement == "new":
                warnings.append("new does not assert unopened guarantee")
            if replacement == "refurbished":
                warnings.append("refurbished is not treated as new retail condition")
            return replacement, warnings

    return text, warnings
