"""
The RealReal internal standard response parser.

Parses BrandProfitFinder internal The RealReal fixture JSON (not an official API format).
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any

from config.constants import CURRENCY_JPY, MARKETPLACE_THEREALREAL
from marketplace.amazon_price_normalizer import parse_jpy_price
from marketplace.therealreal_exceptions import TheRealRealParseError, TheRealRealResponseError
from models.marketplace_listing import MarketplaceListing
from used_luxury.enrichment import UsedItemEnricher

logger = logging.getLogger(__name__)


class TheRealRealSaleStatus(str, Enum):
    """Listing sale status (distinct from item condition and final sale)."""

    ACTIVE = "ACTIVE"
    RESERVED = "RESERVED"
    SOLD = "SOLD"
    INACTIVE = "INACTIVE"
    REMOVED = "REMOVED"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_value(cls, value: Any) -> "TheRealRealSaleStatus":
        if value is None:
            return cls.UNKNOWN
        text = str(value).strip().upper().replace("-", "_").replace(" ", "_")
        try:
            return cls(text)
        except ValueError:
            return cls.UNKNOWN


class TheRealRealInventoryStatus(str, Enum):
    """Inventory availability (distinct from item condition)."""

    IN_STOCK = "IN_STOCK"
    LOW_STOCK = "LOW_STOCK"
    RESERVED = "RESERVED"
    SOLD = "SOLD"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_value(cls, value: Any) -> "TheRealRealInventoryStatus":
        if value is None:
            return cls.UNKNOWN
        text = str(value).strip().upper().replace("-", "_").replace(" ", "_")
        try:
            return cls(text)
        except ValueError:
            return cls.UNKNOWN


@dataclass
class TheRealRealParseResult:
    """Result of parsing a The RealReal search payload."""

    listings: list[MarketplaceListing] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rejected_count: int = 0
    valid_count: int = 0


class TheRealRealResponseParser:
    """Parse internal standard The RealReal JSON into marketplace listings."""

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
        include_final_sale: bool = True,
        include_discounted_only: bool = False,
        allow_unknown_currency: bool = False,
        default_currency: str = CURRENCY_JPY,
    ) -> TheRealRealParseResult:
        """Parse The RealReal internal standard JSON into listings."""
        result = TheRealRealParseResult()
        items = payload.get("items")
        if items is None:
            return result
        if not isinstance(items, list):
            raise TheRealRealParseError("The RealReal items must be a list when present")

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

            sale_status = TheRealRealSaleStatus.from_value(item.get("sale_status"))
            inventory_status = _parse_inventory_status(item.get("inventory"))
            inventory_quantity = _parse_inventory_quantity(item.get("inventory"))
            return_meta = _parse_return_policy_block(item.get("return_policy"))

            filter_warnings = _inventory_sale_warnings(sale_status, inventory_status)
            filter_warnings.extend(return_meta.get("warnings", []))

            if not _should_include_item(
                sale_status,
                inventory_status,
                include_sold=include_sold,
                include_reserved=include_reserved,
                include_unavailable=include_unavailable,
            ):
                result.rejected_count += 1
                continue

            final_sale = return_meta.get("final_sale")
            if not include_final_sale and final_sale is True:
                result.rejected_count += 1
                continue

            discount_meta = _parse_discount_block(item.get("discount"))
            if include_discounted_only and not discount_meta.get("discount_active"):
                result.rejected_count += 1
                continue

            listing, item_warnings = self._parse_item(
                item,
                source_query=source_query,
                allow_unknown_currency=allow_unknown_currency,
                default_currency=default_currency,
                sale_status=sale_status,
                inventory_status=inventory_status,
                inventory_quantity=inventory_quantity,
                discount_meta=discount_meta,
                return_meta=return_meta,
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
        sale_status: TheRealRealSaleStatus,
        inventory_status: TheRealRealInventoryStatus,
        inventory_quantity: int | None,
        discount_meta: dict[str, Any],
        return_meta: dict[str, Any],
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

        listing_url = str(item.get("url") or "").strip()
        image_url = str(item.get("image_url") or "").strip()
        model_number = str(item.get("model_number") or "").strip()
        brand = str(item.get("brand") or "").strip()
        color = str(item.get("color") or "").strip()
        size = str(item.get("size") or "").strip() if item.get("size") is not None else ""

        enrich_input, condition_warnings = _build_enricher_input(item)
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
            "source_marketplace": MARKETPLACE_THEREALREAL,
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
            "source_original_price": original_price_meta.get("original_price"),
            "source_discount_active": discount_meta.get("discount_active"),
            "source_discount_amount": discount_meta.get("discount_amount"),
            "source_discount_rate": discount_meta.get("discount_rate"),
            "source_previous_price": discount_meta.get("previous_price"),
            "source_inventory_status": inventory_status.value,
            "source_inventory_quantity": inventory_quantity,
            "source_final_sale": return_meta.get("final_sale"),
            "therealreal_parse_warnings": "; ".join(warnings) if warnings else None,
        }

        legacy_condition = used_details.condition.value.lower()
        availability = _availability_from_status(sale_status, inventory_status)

        return MarketplaceListing(
            marketplace_name=MARKETPLACE_THEREALREAL,
            listing_id=listing_id or title,
            title=title or listing_id,
            brand=brand,
            model_number=model_number,
            sku="",
            condition=legacy_condition,
            price_jpy=price_jpy,
            shipping_jpy=shipping_jpy,
            shipping_unknown=shipping_unknown,
            seller_name=str(
                item.get("seller_name") or used_details.seller_details.business_name or ""
            ).strip(),
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
            raise TheRealRealResponseError("The RealReal payload must be a JSON object")
        items = payload.get("items")
        if items is not None and not isinstance(items, list):
            raise TheRealRealResponseError("The RealReal items must be a list when present")


def _parse_return_policy_block(block: Any) -> dict[str, Any]:
    """Parse return policy including final_sale (stored in metadata, not condition)."""
    result: dict[str, Any] = {
        "final_sale": None,
        "return_accepted": None,
        "return_period_days": None,
        "warnings": [],
    }
    if not isinstance(block, dict):
        return result

    accepted = block.get("accepted")
    if isinstance(accepted, bool):
        result["return_accepted"] = accepted
    elif accepted is not None:
        result["warnings"].append("return_policy accepted must be boolean or unknown")

    period = block.get("period_days")
    if period is None:
        pass
    elif isinstance(period, bool):
        result["warnings"].append("boolean return period_days rejected")
    elif isinstance(period, int) and period >= 0:
        result["return_period_days"] = period
    else:
        result["warnings"].append("invalid return period_days")

    final_sale_raw = block.get("final_sale")
    if final_sale_raw is None:
        result["final_sale"] = None
    elif isinstance(final_sale_raw, bool):
        result["final_sale"] = final_sale_raw
    else:
        result["warnings"].append("final_sale must be boolean or unknown")

    if result["final_sale"] is True and result["return_accepted"] is True:
        result["warnings"].append("final_sale=true conflicts with return accepted=true")

    return result


def _should_include_item(
    sale_status: TheRealRealSaleStatus,
    inventory_status: TheRealRealInventoryStatus,
    *,
    include_sold: bool,
    include_reserved: bool,
    include_unavailable: bool,
) -> bool:
    if sale_status == TheRealRealSaleStatus.SOLD and not include_sold:
        return False
    if sale_status == TheRealRealSaleStatus.RESERVED and not include_reserved:
        return False
    if sale_status in {
        TheRealRealSaleStatus.INACTIVE,
        TheRealRealSaleStatus.REMOVED,
    } and not include_unavailable:
        return False

    if inventory_status == TheRealRealInventoryStatus.SOLD and not include_sold:
        return False
    if inventory_status == TheRealRealInventoryStatus.RESERVED and not include_reserved:
        return False
    if inventory_status == TheRealRealInventoryStatus.UNAVAILABLE and not include_unavailable:
        return False

    if sale_status in {
        TheRealRealSaleStatus.ACTIVE,
        TheRealRealSaleStatus.UNKNOWN,
    } and inventory_status in {
        TheRealRealInventoryStatus.IN_STOCK,
        TheRealRealInventoryStatus.LOW_STOCK,
        TheRealRealInventoryStatus.UNKNOWN,
    }:
        return True

    if include_sold and (
        sale_status == TheRealRealSaleStatus.SOLD
        or inventory_status == TheRealRealInventoryStatus.SOLD
    ):
        return True
    if include_reserved and (
        sale_status == TheRealRealSaleStatus.RESERVED
        or inventory_status == TheRealRealInventoryStatus.RESERVED
    ):
        return True
    if include_unavailable and (
        sale_status in {TheRealRealSaleStatus.INACTIVE, TheRealRealSaleStatus.REMOVED}
        or inventory_status == TheRealRealInventoryStatus.UNAVAILABLE
    ):
        return True

    return False


def _inventory_sale_warnings(
    sale_status: TheRealRealSaleStatus,
    inventory_status: TheRealRealInventoryStatus,
) -> list[str]:
    warnings: list[str] = []
    if sale_status == TheRealRealSaleStatus.ACTIVE and inventory_status in {
        TheRealRealInventoryStatus.SOLD,
        TheRealRealInventoryStatus.UNAVAILABLE,
    }:
        warnings.append(
            f"sale_status {sale_status.value} conflicts with inventory {inventory_status.value}"
        )
    if sale_status == TheRealRealSaleStatus.SOLD and inventory_status in {
        TheRealRealInventoryStatus.IN_STOCK,
        TheRealRealInventoryStatus.LOW_STOCK,
    }:
        warnings.append(
            f"sale_status {sale_status.value} conflicts with inventory {inventory_status.value}"
        )
    return warnings


def _parse_inventory_status(block: Any) -> TheRealRealInventoryStatus:
    if not isinstance(block, dict):
        return TheRealRealInventoryStatus.UNKNOWN
    return TheRealRealInventoryStatus.from_value(block.get("status"))


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
    sale_status: TheRealRealSaleStatus,
    inventory_status: TheRealRealInventoryStatus,
) -> str:
    if sale_status == TheRealRealSaleStatus.SOLD or inventory_status == TheRealRealInventoryStatus.SOLD:
        return "sold"
    if sale_status == TheRealRealSaleStatus.RESERVED or inventory_status == TheRealRealInventoryStatus.RESERVED:
        return "reserved"
    if inventory_status == TheRealRealInventoryStatus.UNAVAILABLE:
        return "unavailable"
    if sale_status in {TheRealRealSaleStatus.INACTIVE, TheRealRealSaleStatus.REMOVED}:
        return "ended"
    if inventory_status in {
        TheRealRealInventoryStatus.IN_STOCK,
        TheRealRealInventoryStatus.LOW_STOCK,
    }:
        return "in_stock"
    return "unknown"


def _build_enricher_input(item: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Build enricher input, preprocessing condition (not final sale)."""
    warnings: list[str] = []
    result = dict(item)
    condition_block = item.get("condition")
    if isinstance(condition_block, dict):
        raw = str(condition_block.get("raw") or "").strip()
        preprocessed, cond_warnings = preprocess_therealreal_condition(raw)
        warnings.extend(cond_warnings)
        result["condition"] = {
            "raw": raw,
            "description": condition_block.get("description"),
            "normalized": condition_block.get("normalized"),
        }
        if preprocessed and not condition_block.get("normalized"):
            result["condition"]["raw"] = preprocessed
    elif isinstance(condition_block, str):
        preprocessed, cond_warnings = preprocess_therealreal_condition(condition_block)
        warnings.extend(cond_warnings)
        result["condition"] = preprocessed or condition_block
    return result, warnings


def preprocess_therealreal_condition(raw: str | None) -> tuple[str, list[str]]:
    """
    Preprocess The RealReal condition strings before Phase 8 normalization.

    Does not conflate final sale with item condition or upgrade ambiguous wear terms.
    """
    warnings: list[str] = []
    if raw is None or not str(raw).strip():
        return "", warnings

    text = unicodedata.normalize("NFKC", str(raw).strip().lower())
    text = re.sub(r"\s+", " ", text)

    if re.search(r"^final\s*sale$", text):
        warnings.append("final sale is a return policy label, not item condition")
        return "", warnings

    mappings = (
        (r"^pristine$", "pristine"),
        (r"^excellent$", "excellent"),
        (r"^very\s*good$", "very good"),
        (r"^good$", "good"),
        (r"^fair$", "fair"),
        (r"^moderate\s*wear$", "moderate wear"),
        (r"^heavy\s*wear$", "heavy wear"),
        (r"^vintage$", "vintage"),
        (r"^as\s*is$", "as is"),
        (r"^damaged$", "damaged"),
        (r"^for\s*parts$", "for parts"),
    )
    for pattern, replacement in mappings:
        if re.search(pattern, text):
            if replacement == "pristine":
                warnings.append("pristine does not assert unused condition")
            if replacement == "moderate wear":
                warnings.append("moderate wear does not imply good condition grade")
            if replacement == "as is":
                warnings.append("as is condition requires buyer caution")
            return replacement, warnings

    return text, warnings
