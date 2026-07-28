"""
GOAT internal standard response parser.

Parses BrandProfitFinder internal GOAT fixture JSON (not an official API format).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any

from config.constants import CURRENCY_JPY, MARKETPLACE_GOAT
from marketplace.amazon_price_normalizer import parse_jpy_price
from marketplace.goat_exceptions import GoatParseError, GoatResponseError
from models.marketplace_listing import MarketplaceListing
from used_luxury.enrichment import UsedItemEnricher

logger = logging.getLogger(__name__)


class GoatSaleStatus(str, Enum):
    """Listing sale status."""

    ACTIVE = "ACTIVE"
    SOLD = "SOLD"
    UNAVAILABLE = "UNAVAILABLE"
    REMOVED = "REMOVED"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_value(cls, value: Any) -> "GoatSaleStatus":
        if value is None:
            return cls.UNKNOWN
        text = str(value).strip().upper().replace("-", "_").replace(" ", "_")
        try:
            return cls(text)
        except ValueError:
            return cls.UNKNOWN


class GoatInventoryStatus(str, Enum):
    """Inventory availability."""

    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    SOLD = "SOLD"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_value(cls, value: Any) -> "GoatInventoryStatus":
        if value is None:
            return cls.UNKNOWN
        text = str(value).strip().upper().replace("-", "_").replace(" ", "_")
        try:
            return cls(text)
        except ValueError:
            return cls.UNKNOWN


@dataclass
class GoatParseResult:
    """Result of parsing a GOAT search payload."""

    listings: list[MarketplaceListing] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rejected_count: int = 0
    valid_count: int = 0


def normalize_goat_condition(raw: Any) -> tuple[str, list[str]]:
    """
    Normalize GOAT fixture condition values conservatively.

    Returns normalized condition label and warnings.
    """
    warnings: list[str] = []
    if raw is None:
        return "unknown", warnings

    if isinstance(raw, dict):
        text = str(raw.get("raw") or raw.get("label") or "").strip()
        description = str(raw.get("description") or "").strip()
    else:
        text = str(raw).strip()
        description = ""

    if not text:
        return "unknown", warnings

    normalized = text.lower().replace("-", " ").replace("_", " ")
    normalized = " ".join(normalized.split())

    if normalized in {"new", "brand new", "deadstock", "ds"}:
        return "new", warnings
    if normalized in {"new with defects", "new with defect", "new defects"}:
        return "new_with_defects", warnings
    if normalized in {"used", "pre owned", "preowned", "lightly used", "worn"}:
        return "used", warnings
    if normalized == "unknown":
        return "unknown", warnings

    warnings.append(f"unsupported GOAT condition value: {text}")
    if description:
        warnings.append(f"condition description preserved: {description}")
    return "unknown", warnings


def normalize_goat_box_condition(raw: Any) -> tuple[str | None, list[str]]:
    """Normalize box condition metadata without inferring item condition."""
    warnings: list[str] = []
    if raw is None:
        return None, warnings
    if isinstance(raw, dict):
        text = str(raw.get("raw") or raw.get("label") or "").strip()
    else:
        text = str(raw).strip()
    if not text:
        return None, warnings

    normalized = text.lower().replace("-", " ").replace("_", " ")
    normalized = " ".join(normalized.split())
    if normalized in {"good", "original box", "included", "present"}:
        return "good", warnings
    if normalized in {"missing", "no box", "not included"}:
        return "missing", warnings
    if normalized in {"damaged", "bad box", "damaged box"}:
        return "damaged", warnings
    if normalized == "unknown":
        return "unknown", warnings

    warnings.append(f"unsupported GOAT box condition value: {text}")
    return "unknown", warnings


class GoatResponseParser:
    """Parse internal standard GOAT JSON into marketplace listings."""

    def __init__(self, enricher: UsedItemEnricher | None = None) -> None:
        self._enricher = enricher or UsedItemEnricher()

    def parse(
        self,
        payload: dict[str, object],
        *,
        source_query: str = "",
        include_unavailable: bool = False,
        include_sold: bool = False,
        include_new: bool = True,
        include_used: bool = True,
        allow_unknown_currency: bool = False,
        default_currency: str = CURRENCY_JPY,
    ) -> GoatParseResult:
        """Parse GOAT internal standard JSON into listings."""
        result = GoatParseResult()
        items = payload.get("items")
        if items is None:
            return result
        if not isinstance(items, list):
            raise GoatParseError("GOAT items must be a list when present")

        seen_ids: set[str] = set()
        for item in items:
            if not isinstance(item, dict):
                result.rejected_count += 1
                result.warnings.append("skipped non-object item")
                continue

            listing_id = str(item.get("listing_id") or "").strip()
            if listing_id and listing_id in seen_ids:
                result.warnings.append(f"skipped duplicate listing_id: {listing_id}")
                result.rejected_count += 1
                continue

            sale_status = GoatSaleStatus.from_value(item.get("sale_status"))
            inventory_status = _parse_inventory_status(item.get("inventory"))
            if not _should_include_item(
                sale_status,
                inventory_status,
                include_sold=include_sold,
                include_unavailable=include_unavailable,
            ):
                result.rejected_count += 1
                continue

            condition_label, condition_warnings = normalize_goat_condition(item.get("condition"))
            if condition_label == "new" and not include_new:
                result.rejected_count += 1
                continue
            if condition_label in {"used", "new_with_defects"} and not include_used:
                result.rejected_count += 1
                continue

            listing, item_warnings = self._parse_item(
                item,
                source_query=source_query,
                allow_unknown_currency=allow_unknown_currency,
                default_currency=default_currency,
                sale_status=sale_status,
                inventory_status=inventory_status,
                condition_label=condition_label,
                condition_warnings=condition_warnings,
            )
            if listing is None:
                result.rejected_count += 1
                result.warnings.extend(item_warnings)
                continue

            if listing_id:
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
        sale_status: GoatSaleStatus,
        inventory_status: GoatInventoryStatus,
        condition_label: str,
        condition_warnings: list[str],
    ) -> tuple[MarketplaceListing | None, list[str]]:
        warnings: list[str] = list(condition_warnings)
        listing_id = str(item.get("listing_id") or "").strip()
        title = str(item.get("title") or "").strip()
        if not title:
            warnings.append(f"skipped item without title (listing_id={listing_id or 'unknown'})")
            return None, warnings

        price_jpy, currency, price_warnings = _parse_price_block(
            item.get("price"),
            default_currency=default_currency,
            allow_unknown_currency=allow_unknown_currency,
        )
        warnings.extend(price_warnings)
        if price_jpy is None:
            warnings.append(f"skipped item without valid price (listing_id={listing_id or title})")
            return None, warnings

        shipping_jpy, shipping_unknown, ship_warnings = _parse_shipping_block(item.get("shipping"))
        warnings.extend(ship_warnings)
        fees_known, fees_warnings = _parse_fees_block(item.get("fees"))
        warnings.extend(fees_warnings)

        box_condition, box_warnings = normalize_goat_box_condition(item.get("box_condition"))
        warnings.extend(box_warnings)

        listing_url = str(item.get("url") or "").strip()
        image_url = str(item.get("image_url") or "").strip()
        brand = str(item.get("brand") or "").strip()
        model_number = str(item.get("model") or item.get("model_number") or "").strip()
        style_code = str(item.get("style_code") or "").strip()
        sku = str(item.get("sku") or "").strip()
        colorway = str(item.get("colorway") or item.get("color") or "").strip()
        size = str(item.get("size") or "").strip() if item.get("size") is not None else ""
        size_system = str(item.get("size_system") or "").strip() or None
        seller_region = str(item.get("seller_region") or "").strip() or None
        category = str(item.get("category") or "").strip() or None
        release_year = item.get("release_year") if isinstance(item.get("release_year"), int) else None

        enrich_input = _build_enricher_input(item, condition_label)
        used_details = self._enricher.enrich(
            enrich_input,
            price_jpy=price_jpy,
            shipping_unknown=shipping_unknown,
            listing_url=listing_url,
            image_url=image_url,
            model_number=model_number or style_code,
        )
        if used_details.warnings:
            warnings.extend(used_details.warnings)

        parse_warnings = (
            item.get("metadata", {}).get("parse_warnings")
            if isinstance(item.get("metadata"), dict)
            else None
        )
        if isinstance(parse_warnings, list):
            warnings.extend(str(w) for w in parse_warnings)

        source_metadata: dict[str, Any] = {
            "source_marketplace": MARKETPLACE_GOAT,
            "source_listing_id": listing_id,
            "source_currency": currency,
            "source_shipping_known": not shipping_unknown,
            "source_sale_status": sale_status.value,
            "source_inventory_status": inventory_status.value,
            "source_category": category,
            "source_color": colorway or None,
            "source_size": size or None,
            "source_style_code": style_code or None,
            "source_product_id": str(item.get("product_id") or "").strip() or None,
            "source_goat_style_code": style_code or None,
            "source_goat_sku": sku or None,
            "source_goat_size_system": size_system,
            "source_goat_colorway": colorway or None,
            "source_goat_box_condition": box_condition,
            "source_goat_seller_region": seller_region,
            "source_goat_release_year": release_year,
            "source_goat_condition_normalized": condition_label,
            "source_goat_fees_known": fees_known,
            "goat_parse_warnings": "; ".join(warnings) if warnings else None,
        }

        availability = _availability_from_status(sale_status, inventory_status)
        legacy_condition = used_details.condition.value.lower()

        return MarketplaceListing(
            marketplace_name=MARKETPLACE_GOAT,
            listing_id=listing_id or title,
            title=title,
            brand=brand,
            model_number=model_number,
            sku=sku or style_code,
            condition=legacy_condition,
            price_jpy=price_jpy,
            shipping_jpy=shipping_jpy,
            shipping_unknown=shipping_unknown,
            seller_name="",
            listing_url=listing_url,
            image_url=image_url,
            availability=availability,
            source_query=source_query,
            currency=currency,
            used_item_details=used_details,
            source_metadata=source_metadata,
        ), warnings

    @staticmethod
    def validate_payload(payload: dict[str, object]) -> None:
        """Validate top-level payload structure."""
        if not isinstance(payload, dict):
            raise GoatResponseError("GOAT payload must be a JSON object")
        items = payload.get("items")
        if items is not None and not isinstance(items, list):
            raise GoatResponseError("GOAT items must be a list when present")


def _parse_inventory_status(block: Any) -> GoatInventoryStatus:
    if isinstance(block, dict):
        return GoatInventoryStatus.from_value(block.get("status"))
    return GoatInventoryStatus.UNKNOWN


def _should_include_item(
    sale_status: GoatSaleStatus,
    inventory_status: GoatInventoryStatus,
    *,
    include_sold: bool,
    include_unavailable: bool,
) -> bool:
    if sale_status == GoatSaleStatus.SOLD and not include_sold:
        return False
    if sale_status in {GoatSaleStatus.UNAVAILABLE, GoatSaleStatus.REMOVED} and not include_unavailable:
        return False
    if inventory_status == GoatInventoryStatus.SOLD and not include_sold:
        return False
    if inventory_status == GoatInventoryStatus.UNAVAILABLE and not include_unavailable:
        return False
    return True


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
    if amount_raw is None:
        return None, default_currency, ["missing price amount"]
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

    amount = parse_jpy_price(amount_raw)
    if amount is None:
        warnings.append("invalid shipping amount ignored")
        return None, True, warnings
    return amount, False, warnings


def _parse_fees_block(block: Any) -> tuple[bool | None, list[str]]:
    warnings: list[str] = []
    if block is None:
        return None, warnings
    if not isinstance(block, dict):
        return None, ["invalid fees block"]
    known = block.get("known")
    if isinstance(known, bool):
        return known, warnings
    return None, warnings


def _build_enricher_input(item: dict[str, Any], condition_label: str) -> dict[str, Any]:
    condition_raw = condition_label
    if isinstance(item.get("condition"), dict):
        condition_raw = str(item["condition"].get("raw") or condition_label)
    return {
        "condition": {"raw": condition_raw},
        "authentication": item.get("authentication") if isinstance(item.get("authentication"), dict) else {},
        "seller": item.get("seller") if isinstance(item.get("seller"), dict) else {},
        "accessories": item.get("accessories") if isinstance(item.get("accessories"), dict) else {},
        "defects": item.get("defects") if isinstance(item.get("defects"), dict) else {},
    }


def _availability_from_status(
    sale_status: GoatSaleStatus,
    inventory_status: GoatInventoryStatus,
) -> str:
    if sale_status == GoatSaleStatus.SOLD or inventory_status == GoatInventoryStatus.SOLD:
        return "sold"
    if sale_status in {GoatSaleStatus.UNAVAILABLE, GoatSaleStatus.REMOVED}:
        return "unavailable"
    if inventory_status == GoatInventoryStatus.UNAVAILABLE:
        return "unavailable"
    if sale_status == GoatSaleStatus.ACTIVE or inventory_status == GoatInventoryStatus.AVAILABLE:
        return "available"
    return "unknown"
