"""
Chrono24 internal standard response parser.

Parses BrandProfitFinder internal Chrono24 fixture JSON (not an official API format).
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any

from config.constants import CURRENCY_JPY, MARKETPLACE_CHRONO24
from marketplace.amazon_price_normalizer import parse_jpy_price
from marketplace.chrono24_exceptions import Chrono24ParseError, Chrono24ResponseError
from models.marketplace_listing import MarketplaceListing
from models.seller_info import SellerType
from used_luxury.enrichment import UsedItemEnricher

logger = logging.getLogger(__name__)

_CURRENT_YEAR = 2026


class Chrono24SaleStatus(str, Enum):
    """Listing sale status (distinct from item condition)."""

    ACTIVE = "ACTIVE"
    RESERVED = "RESERVED"
    SOLD = "SOLD"
    INACTIVE = "INACTIVE"
    REMOVED = "REMOVED"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_value(cls, value: Any) -> "Chrono24SaleStatus":
        if value is None:
            return cls.UNKNOWN
        text = str(value).strip().upper().replace("-", "_").replace(" ", "_")
        try:
            return cls(text)
        except ValueError:
            return cls.UNKNOWN


class Chrono24InventoryStatus(str, Enum):
    """Inventory availability (distinct from item condition)."""

    IN_STOCK = "IN_STOCK"
    RESERVED = "RESERVED"
    SOLD = "SOLD"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_value(cls, value: Any) -> "Chrono24InventoryStatus":
        if value is None:
            return cls.UNKNOWN
        text = str(value).strip().upper().replace("-", "_").replace(" ", "_")
        try:
            return cls(text)
        except ValueError:
            return cls.UNKNOWN


class WatchMovementType(str, Enum):
    """Normalized watch movement categories."""

    AUTOMATIC = "AUTOMATIC"
    MANUAL = "MANUAL"
    QUARTZ = "QUARTZ"
    SOLAR = "SOLAR"
    KINETIC = "KINETIC"
    SPRING_DRIVE = "SPRING_DRIVE"
    SMART = "SMART"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_value(cls, value: Any) -> "WatchMovementType":
        if value is None:
            return cls.UNKNOWN
        text = str(value).strip().upper().replace("-", "_").replace(" ", "_")
        aliases = {"SPRINGDRIVE": cls.SPRING_DRIVE}
        if text in aliases:
            return aliases[text]
        try:
            return cls(text)
        except ValueError:
            return cls.UNKNOWN


@dataclass
class Chrono24ParseResult:
    """Result of parsing a Chrono24 search payload."""

    listings: list[MarketplaceListing] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rejected_count: int = 0
    valid_count: int = 0


class Chrono24ResponseParser:
    """Parse internal standard Chrono24 JSON into marketplace listings."""

    def __init__(self, enricher: UsedItemEnricher | None = None) -> None:
        self._enricher = enricher or UsedItemEnricher()

    def parse(
        self,
        payload: dict[str, object],
        *,
        source_query: str = "",
        include_sold: bool = False,
        include_reserved: bool = False,
        include_unavailable: bool = False,
        include_discounted_only: bool = False,
        include_negotiable_only: bool = False,
        require_verified_seller: bool = False,
        require_trusted_seller: bool = False,
        include_private_sellers: bool = True,
        include_professional_dealers: bool = True,
        allow_unknown_currency: bool = False,
        default_currency: str = CURRENCY_JPY,
    ) -> Chrono24ParseResult:
        """Parse Chrono24 internal standard JSON into listings."""
        result = Chrono24ParseResult()
        items = payload.get("items")
        if items is None:
            return result
        if not isinstance(items, list):
            raise Chrono24ParseError("Chrono24 items must be a list when present")

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

            sale_status = Chrono24SaleStatus.from_value(item.get("sale_status"))
            inventory_status = _parse_inventory_status(item.get("inventory"))
            inventory_quantity = _parse_inventory_quantity(item.get("inventory"))
            filter_warnings = _inventory_sale_warnings(sale_status, inventory_status)

            if not _should_include_item(
                sale_status,
                inventory_status,
                include_sold=include_sold,
                include_reserved=include_reserved,
                include_unavailable=include_unavailable,
            ):
                result.rejected_count += 1
                continue

            discount_meta = _parse_discount_block(item.get("discount"))
            if include_discounted_only and not discount_meta.get("discount_active"):
                result.rejected_count += 1
                continue

            negotiation_meta = _parse_negotiation_block(item.get("negotiation"))
            if include_negotiable_only and negotiation_meta.get("negotiation_enabled") is not True:
                result.rejected_count += 1
                continue

            seller_meta = _parse_seller_metadata(item.get("seller"))
            filter_warnings.extend(seller_meta.get("warnings", []))
            if require_verified_seller and seller_meta.get("seller_verified") is not True:
                result.rejected_count += 1
                continue
            if require_trusted_seller and seller_meta.get("seller_trusted") is not True:
                result.rejected_count += 1
                continue
            if not _should_include_seller_type(
                seller_meta.get("seller_type"),
                include_private_sellers=include_private_sellers,
                include_professional_dealers=include_professional_dealers,
            ):
                result.rejected_count += 1
                continue

            watch_meta = _parse_watch_details_block(item.get("watch_details"))
            filter_warnings.extend(watch_meta.get("warnings", []))

            listing, item_warnings = self._parse_item(
                item,
                source_query=source_query,
                allow_unknown_currency=allow_unknown_currency,
                default_currency=default_currency,
                sale_status=sale_status,
                inventory_status=inventory_status,
                inventory_quantity=inventory_quantity,
                discount_meta=discount_meta,
                negotiation_meta=negotiation_meta,
                seller_meta=seller_meta,
                watch_meta=watch_meta,
                extra_warnings=filter_warnings,
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
        sale_status: Chrono24SaleStatus,
        inventory_status: Chrono24InventoryStatus,
        inventory_quantity: int | None,
        discount_meta: dict[str, Any],
        negotiation_meta: dict[str, Any],
        seller_meta: dict[str, Any],
        watch_meta: dict[str, Any],
        extra_warnings: list[str],
    ) -> tuple[MarketplaceListing | None, list[str]]:
        warnings: list[str] = list(extra_warnings)
        listing_id = str(item.get("listing_id") or "").strip()
        title = str(item.get("title") or "").strip()
        if not listing_id and not title:
            warnings.append("skipped item without listing_id and title")
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

        original_price_meta = _parse_original_price_block(
            item.get("original_price"),
            default_currency=default_currency,
            allow_unknown_currency=allow_unknown_currency,
            current_price=price_jpy,
        )
        warnings.extend(original_price_meta.pop("warnings", []))

        if discount_meta.get("discount_inconsistent"):
            warnings.append("discount amount and rate are inconsistent")

        warnings.extend(negotiation_meta.pop("warnings", []))
        neg_warning = _warn_minimum_offer_above_price(
            negotiation_meta.get("minimum_offer"),
            price_jpy,
        )
        if neg_warning:
            warnings.append(neg_warning)

        listing_url = str(item.get("url") or "").strip()
        image_url = str(item.get("image_url") or "").strip()
        model_number = str(item.get("model_number") or "").strip()
        reference_number = str(item.get("reference_number") or "").strip()
        if not model_number and reference_number:
            model_number = reference_number

        brand = str(item.get("brand") or "").strip()
        color = str(item.get("color") or "").strip()
        size = str(item.get("size") or "").strip() if item.get("size") is not None else ""

        enrich_input, condition_warnings = _build_enricher_input(
            item,
            seller_meta.get("seller_for_enricher"),
        )
        warnings.extend(condition_warnings)

        used_details = self._enricher.enrich(
            enrich_input,
            price_jpy=price_jpy,
            shipping_unknown=shipping_unknown,
            listing_url=listing_url,
            image_url=image_url,
            model_number=model_number,
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
            "source_marketplace": MARKETPLACE_CHRONO24,
            "source_listing_id": listing_id,
            "source_currency": currency,
            "source_shipping_known": not shipping_unknown,
            "source_sale_status": sale_status.value,
            "source_category": str(item.get("category") or "").strip() or None,
            "source_sub_category": str(item.get("sub_category") or "").strip() or None,
            "source_material": str(item.get("material") or "").strip() or None,
            "source_gender": str(item.get("gender") or "").strip() or None,
            "source_listed_at": str(item.get("listed_at") or "").strip() or None,
            "source_color": color or None,
            "source_size": size or None,
            "source_reference_number": reference_number or None,
            "source_movement_type": watch_meta.get("movement_type"),
            "source_movement_type_raw": watch_meta.get("movement_type_raw"),
            "source_caliber": watch_meta.get("caliber"),
            "source_case_material": watch_meta.get("case_material"),
            "source_case_diameter_mm": watch_meta.get("case_diameter_mm"),
            "source_bezel_material": watch_meta.get("bezel_material"),
            "source_crystal": watch_meta.get("crystal"),
            "source_dial_color": watch_meta.get("dial_color"),
            "source_bracelet_material": watch_meta.get("bracelet_material"),
            "source_bracelet_color": watch_meta.get("bracelet_color"),
            "source_production_year": watch_meta.get("production_year"),
            "source_water_resistance_m": watch_meta.get("water_resistance_m"),
            "source_power_reserve_hours": watch_meta.get("power_reserve_hours"),
            "source_watch_functions": watch_meta.get("watch_functions"),
            "source_original_price": original_price_meta.get("original_price"),
            "source_discount_active": discount_meta.get("discount_active"),
            "source_discount_amount": discount_meta.get("discount_amount"),
            "source_discount_rate": discount_meta.get("discount_rate"),
            "source_previous_price": discount_meta.get("previous_price"),
            "source_inventory_status": inventory_status.value,
            "source_inventory_quantity": inventory_quantity,
            "source_negotiation_enabled": negotiation_meta.get("negotiation_enabled"),
            "source_minimum_offer": negotiation_meta.get("minimum_offer"),
            "source_negotiation_currency": negotiation_meta.get("negotiation_currency"),
            "source_seller_trusted": seller_meta.get("seller_trusted"),
            "source_seller_transactions": seller_meta.get("seller_transactions"),
            "chrono24_parse_warnings": "; ".join(warnings) if warnings else None,
        }

        legacy_condition = used_details.condition.value.lower()
        availability = _availability_from_status(sale_status, inventory_status)

        return MarketplaceListing(
            marketplace_name=MARKETPLACE_CHRONO24,
            listing_id=listing_id or title,
            title=title or listing_id,
            brand=brand,
            model_number=model_number,
            sku="",
            condition=legacy_condition,
            price_jpy=price_jpy,
            shipping_jpy=shipping_jpy,
            shipping_unknown=shipping_unknown,
            seller_name="",
            seller_rating=used_details.seller_details.seller_rating,
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
            raise Chrono24ResponseError("Chrono24 payload must be a JSON object")
        items = payload.get("items")
        if items is not None and not isinstance(items, list):
            raise Chrono24ResponseError("Chrono24 items must be a list when present")


def _parse_watch_details_block(block: Any) -> dict[str, Any]:
    """Parse watch-specific metadata without asserting authenticity."""
    result: dict[str, Any] = {
        "movement_type": None,
        "movement_type_raw": None,
        "caliber": None,
        "case_material": None,
        "case_diameter_mm": None,
        "bezel_material": None,
        "crystal": None,
        "dial_color": None,
        "bracelet_material": None,
        "bracelet_color": None,
        "production_year": None,
        "water_resistance_m": None,
        "power_reserve_hours": None,
        "watch_functions": None,
        "warnings": [],
    }
    if not isinstance(block, dict):
        return result

    raw_movement = block.get("movement_type")
    if raw_movement is not None:
        result["movement_type_raw"] = str(raw_movement).strip() or None
        normalized = WatchMovementType.from_value(raw_movement)
        if normalized == WatchMovementType.UNKNOWN and result["movement_type_raw"]:
            result["warnings"].append(f"unknown movement type: {result['movement_type_raw']}")
        result["movement_type"] = normalized.value if normalized != WatchMovementType.UNKNOWN else None

    caliber = block.get("caliber")
    if caliber is not None:
        result["caliber"] = str(caliber).strip() or None

    for key in (
        "case_material",
        "bezel_material",
        "crystal",
        "dial_color",
        "bracelet_material",
        "bracelet_color",
    ):
        value = block.get(key)
        if value is not None:
            result[key] = str(value).strip().upper() or None

    diameter = block.get("case_diameter_mm")
    if diameter is not None:
        if isinstance(diameter, bool):
            result["warnings"].append("boolean case_diameter_mm rejected")
        else:
            try:
                diameter_value = float(diameter)
                if diameter_value > 0:
                    result["case_diameter_mm"] = diameter_value
                else:
                    result["warnings"].append("case_diameter_mm must be positive")
            except (TypeError, ValueError):
                result["warnings"].append("invalid case_diameter_mm")

    year = block.get("production_year")
    if year is not None:
        if isinstance(year, bool) or not isinstance(year, int) or not 1900 <= year <= 2100:
            result["warnings"].append("invalid production_year")
        else:
            if year > _CURRENT_YEAR:
                result["warnings"].append("production_year is in the future")
            result["production_year"] = year

    water = block.get("water_resistance_m")
    if water is not None:
        if isinstance(water, bool) or not isinstance(water, int) or water < 0:
            result["warnings"].append("invalid water_resistance_m")
        else:
            result["water_resistance_m"] = water

    reserve = block.get("power_reserve_hours")
    if reserve is not None:
        if isinstance(reserve, bool) or not isinstance(reserve, int) or reserve < 0:
            result["warnings"].append("invalid power_reserve_hours")
        else:
            result["power_reserve_hours"] = reserve

    functions = block.get("functions")
    if functions is not None:
        if isinstance(functions, list):
            cleaned = [str(item).strip() for item in functions if item is not None and str(item).strip()]
            result["watch_functions"] = ", ".join(cleaned) if cleaned else None
        else:
            result["warnings"].append("watch functions must be a list")

    return result


def _parse_seller_metadata(block: Any) -> dict[str, Any]:
    """Validate Chrono24 seller block and extract metadata."""
    result: dict[str, Any] = {
        "seller_for_enricher": None,
        "seller_transactions": None,
        "seller_verified": None,
        "seller_trusted": None,
        "seller_type": SellerType.UNKNOWN,
        "warnings": [],
    }
    if not isinstance(block, dict):
        return result

    seller_for_enricher = dict(block)
    seller_type_raw = block.get("type")
    if seller_type_raw is not None:
        result["seller_type"] = SellerType.from_value(seller_type_raw)

    rating = block.get("rating")
    if rating is not None:
        if isinstance(rating, bool):
            result["warnings"].append("boolean seller rating rejected")
            seller_for_enricher.pop("rating", None)
        else:
            try:
                rating_value = float(rating)
                if 0 <= rating_value <= 5:
                    seller_for_enricher["rating"] = rating_value
                else:
                    result["warnings"].append("seller rating out of range")
                    seller_for_enricher.pop("rating", None)
            except (TypeError, ValueError):
                result["warnings"].append("invalid seller rating")
                seller_for_enricher.pop("rating", None)

    review_count = block.get("review_count")
    if review_count is not None:
        if isinstance(review_count, bool) or not isinstance(review_count, int) or review_count < 0:
            result["warnings"].append("invalid seller review_count")
            seller_for_enricher.pop("review_count", None)

    transactions = block.get("transactions")
    if transactions is not None:
        if isinstance(transactions, bool) or not isinstance(transactions, int) or transactions < 0:
            result["warnings"].append("invalid seller transactions")
        else:
            result["seller_transactions"] = transactions

    verified = block.get("verified")
    if isinstance(verified, bool):
        result["seller_verified"] = verified
    elif verified is not None:
        result["warnings"].append("seller verified must be boolean or unknown")

    trusted = block.get("trusted_seller")
    if isinstance(trusted, bool):
        result["seller_trusted"] = trusted
    elif trusted is not None:
        result["warnings"].append("trusted_seller must be boolean or unknown")

    result["seller_for_enricher"] = seller_for_enricher
    return result


def _should_include_seller_type(
    seller_type: SellerType,
    *,
    include_private_sellers: bool,
    include_professional_dealers: bool,
) -> bool:
    if not include_private_sellers and not include_professional_dealers:
        return seller_type not in {SellerType.PRIVATE_SELLER, SellerType.PROFESSIONAL_SELLER}
    if seller_type == SellerType.PRIVATE_SELLER and not include_private_sellers:
        return False
    if seller_type == SellerType.PROFESSIONAL_SELLER and not include_professional_dealers:
        return False
    return True


def _parse_negotiation_block(block: Any) -> dict[str, Any]:
    """Parse price negotiation metadata without applying to purchase price."""
    result: dict[str, Any] = {
        "negotiation_enabled": None,
        "minimum_offer": None,
        "negotiation_currency": None,
        "warnings": [],
    }
    if not isinstance(block, dict):
        return result

    enabled = block.get("enabled")
    if isinstance(enabled, bool):
        result["negotiation_enabled"] = enabled
    elif enabled is not None:
        result["warnings"].append("negotiation enabled must be boolean or unknown")

    minimum_raw = block.get("minimum_offer")
    if minimum_raw is not None:
        if isinstance(minimum_raw, bool):
            result["warnings"].append("boolean minimum_offer rejected")
        else:
            minimum = parse_jpy_price(minimum_raw)
            if minimum is not None and minimum >= 0:
                result["minimum_offer"] = float(minimum)
            else:
                result["warnings"].append("invalid minimum_offer")

    currency = block.get("currency")
    if currency is not None:
        result["negotiation_currency"] = str(currency).strip().upper() or None

    return result


def _should_include_item(
    sale_status: Chrono24SaleStatus,
    inventory_status: Chrono24InventoryStatus,
    *,
    include_sold: bool,
    include_reserved: bool,
    include_unavailable: bool,
) -> bool:
    if sale_status == Chrono24SaleStatus.SOLD and not include_sold:
        return False
    if sale_status == Chrono24SaleStatus.RESERVED and not include_reserved:
        return False
    if sale_status in {
        Chrono24SaleStatus.INACTIVE,
        Chrono24SaleStatus.REMOVED,
    } and not include_unavailable:
        return False

    if inventory_status == Chrono24InventoryStatus.SOLD and not include_sold:
        return False
    if inventory_status == Chrono24InventoryStatus.RESERVED and not include_reserved:
        return False
    if inventory_status == Chrono24InventoryStatus.UNAVAILABLE and not include_unavailable:
        return False

    if sale_status in {
        Chrono24SaleStatus.ACTIVE,
        Chrono24SaleStatus.UNKNOWN,
    } and inventory_status in {
        Chrono24InventoryStatus.IN_STOCK,
        Chrono24InventoryStatus.UNKNOWN,
    }:
        return True

    if include_sold and (
        sale_status == Chrono24SaleStatus.SOLD
        or inventory_status == Chrono24InventoryStatus.SOLD
    ):
        return True
    if include_reserved and (
        sale_status == Chrono24SaleStatus.RESERVED
        or inventory_status == Chrono24InventoryStatus.RESERVED
    ):
        return True
    if include_unavailable and (
        sale_status in {Chrono24SaleStatus.INACTIVE, Chrono24SaleStatus.REMOVED}
        or inventory_status == Chrono24InventoryStatus.UNAVAILABLE
    ):
        return True

    return False


def _inventory_sale_warnings(
    sale_status: Chrono24SaleStatus,
    inventory_status: Chrono24InventoryStatus,
) -> list[str]:
    warnings: list[str] = []
    if sale_status == Chrono24SaleStatus.ACTIVE and inventory_status in {
        Chrono24InventoryStatus.SOLD,
        Chrono24InventoryStatus.UNAVAILABLE,
    }:
        warnings.append(
            f"sale_status {sale_status.value} conflicts with inventory {inventory_status.value}"
        )
    if sale_status == Chrono24SaleStatus.SOLD and inventory_status == Chrono24InventoryStatus.IN_STOCK:
        warnings.append(
            f"sale_status {sale_status.value} conflicts with inventory {inventory_status.value}"
        )
    return warnings


def _parse_inventory_status(block: Any) -> Chrono24InventoryStatus:
    if not isinstance(block, dict):
        return Chrono24InventoryStatus.UNKNOWN
    return Chrono24InventoryStatus.from_value(block.get("status"))


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
    sale_status: Chrono24SaleStatus,
    inventory_status: Chrono24InventoryStatus,
) -> str:
    if sale_status == Chrono24SaleStatus.SOLD or inventory_status == Chrono24InventoryStatus.SOLD:
        return "sold"
    if sale_status == Chrono24SaleStatus.RESERVED or inventory_status == Chrono24InventoryStatus.RESERVED:
        return "reserved"
    if inventory_status == Chrono24InventoryStatus.UNAVAILABLE:
        return "unavailable"
    if sale_status in {Chrono24SaleStatus.INACTIVE, Chrono24SaleStatus.REMOVED}:
        return "ended"
    if inventory_status == Chrono24InventoryStatus.IN_STOCK:
        return "in_stock"
    return "unknown"


def _build_enricher_input(
    item: dict[str, Any],
    seller_override: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[str]]:
    """Build enricher input with Chrono24 condition preprocessing."""
    warnings: list[str] = []
    result = dict(item)
    if seller_override is not None:
        result["seller"] = seller_override

    condition_block = item.get("condition")
    if isinstance(condition_block, dict):
        raw = str(condition_block.get("raw") or "").strip()
        preprocessed, cond_warnings = preprocess_chrono24_condition(raw)
        warnings.extend(cond_warnings)
        result["condition"] = {
            "raw": raw,
            "description": condition_block.get("description"),
            "normalized": condition_block.get("normalized"),
        }
        if preprocessed and not condition_block.get("normalized"):
            result["condition"]["raw"] = preprocessed
    elif isinstance(condition_block, str):
        preprocessed, cond_warnings = preprocess_chrono24_condition(condition_block)
        warnings.extend(cond_warnings)
        result["condition"] = preprocessed or condition_block
    return result, warnings


def preprocess_chrono24_condition(raw: str | None) -> tuple[str, list[str]]:
    """
    Preprocess Chrono24 condition strings before Phase 8 normalization.

    Does not upgrade ambiguous wear terms or conflate accessories with condition.
    """
    warnings: list[str] = []
    if raw is None or not str(raw).strip():
        return "", warnings

    text = unicodedata.normalize("NFKC", str(raw).strip().lower())
    text = re.sub(r"\s+", " ", text)

    mappings = (
        (r"^new$", "new"),
        (r"^unworn$", "unworn"),
        (r"^mint$", "mint"),
        (r"^like\s*new$", "like new"),
        (r"^excellent$", "excellent"),
        (r"^very\s*good$", "very good"),
        (r"^good$", "good"),
        (r"^fair$", "fair"),
        (r"^poor$", "poor"),
        (r"^incomplete$", "incomplete"),
        (r"^vintage$", "vintage"),
        (r"^modified$", "modified"),
        (r"^customized$", "customized"),
        (r"^as\s*is$", "as is"),
        (r"^damaged$", "damaged"),
        (r"^for\s*parts$", "for parts"),
        (r"^記載なし$", ""),
    )
    for pattern, replacement in mappings:
        if re.search(pattern, text):
            if replacement == "new":
                warnings.append("new does not assert completely unused condition")
            if replacement == "unworn":
                warnings.append("unworn indicates no wear history; storage wear possible")
            if replacement == "mint":
                warnings.append("mint does not assert unused condition")
            if replacement == "like new":
                warnings.append("like new does not auto-upgrade to unused")
            if replacement == "good":
                warnings.append("good alone does not imply high condition grade")
            if replacement == "vintage":
                warnings.append("vintage indicates age; not upgraded to good condition")
            if replacement == "modified":
                warnings.append("modified may indicate non-original parts or changes")
            if replacement == "customized":
                warnings.append("customized may indicate non-original specification")
            if replacement == "as is":
                warnings.append("as is condition requires buyer caution")
            if replacement == "damaged":
                warnings.append("damaged condition normalized conservatively")
            if replacement == "for parts":
                warnings.append("for parts indicates lowest usable condition")
            return replacement, warnings

    return text, warnings


def _warn_minimum_offer_above_price(
    minimum_offer: float | None,
    current_price: Decimal,
) -> str | None:
    """Return warning when minimum offer exceeds current listing price."""
    if minimum_offer is None:
        return None
    if minimum_offer > float(current_price):
        return "minimum_offer exceeds current price"
    return None
