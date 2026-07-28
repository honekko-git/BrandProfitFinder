"""
Grailed internal standard response parser.

Parses BrandProfitFinder internal Grailed fixture JSON (not an official API format).
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any

from config.constants import CURRENCY_JPY, MARKETPLACE_GRAILED
from marketplace.amazon_price_normalizer import parse_jpy_price
from marketplace.grailed_exceptions import GrailedParseError, GrailedResponseError
from models.marketplace_listing import MarketplaceListing
from used_luxury.enrichment import UsedItemEnricher

logger = logging.getLogger(__name__)


class GrailedSaleStatus(str, Enum):
    """Listing sale status (distinct from item condition)."""

    ACTIVE = "ACTIVE"
    RESERVED = "RESERVED"
    SOLD = "SOLD"
    INACTIVE = "INACTIVE"
    REMOVED = "REMOVED"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_value(cls, value: Any) -> "GrailedSaleStatus":
        if value is None:
            return cls.UNKNOWN
        text = str(value).strip().upper().replace("-", "_").replace(" ", "_")
        try:
            return cls(text)
        except ValueError:
            return cls.UNKNOWN


class GrailedInventoryStatus(str, Enum):
    """Inventory availability (distinct from item condition)."""

    IN_STOCK = "IN_STOCK"
    RESERVED = "RESERVED"
    SOLD = "SOLD"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_value(cls, value: Any) -> "GrailedInventoryStatus":
        if value is None:
            return cls.UNKNOWN
        text = str(value).strip().upper().replace("-", "_").replace(" ", "_")
        try:
            return cls(text)
        except ValueError:
            return cls.UNKNOWN


@dataclass
class GrailedParseResult:
    """Result of parsing a Grailed search payload."""

    listings: list[MarketplaceListing] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rejected_count: int = 0
    valid_count: int = 0


class GrailedResponseParser:
    """Parse internal standard Grailed JSON into marketplace listings."""

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
        include_offer_enabled_only: bool = False,
        require_verified_seller: bool = False,
        allow_unknown_currency: bool = False,
        default_currency: str = CURRENCY_JPY,
    ) -> GrailedParseResult:
        """Parse Grailed internal standard JSON into listings."""
        result = GrailedParseResult()
        items = payload.get("items")
        if items is None:
            return result
        if not isinstance(items, list):
            raise GrailedParseError("Grailed items must be a list when present")

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

            sale_status = GrailedSaleStatus.from_value(item.get("sale_status"))
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

            offer_meta = _parse_offer_block(item.get("offer"))
            if include_offer_enabled_only and offer_meta.get("offer_enabled") is not True:
                result.rejected_count += 1
                continue

            seller_meta = _parse_seller_metadata(item.get("seller"))
            filter_warnings.extend(seller_meta.get("warnings", []))
            if require_verified_seller and seller_meta.get("seller_verified") is not True:
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
                offer_meta=offer_meta,
                seller_meta=seller_meta,
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
        sale_status: GrailedSaleStatus,
        inventory_status: GrailedInventoryStatus,
        inventory_quantity: int | None,
        discount_meta: dict[str, Any],
        offer_meta: dict[str, Any],
        seller_meta: dict[str, Any],
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

        warnings.extend(offer_meta.pop("warnings", []))
        offer_warning = warn_minimum_offer_above_price(offer_meta.get("minimum_offer"), price_jpy)
        if offer_warning:
            warnings.append(offer_warning)

        listing_url = str(item.get("url") or "").strip()
        image_url = str(item.get("image_url") or "").strip()
        model_number = str(item.get("model_number") or "").strip()
        brand = str(item.get("brand") or "").strip()
        color = str(item.get("color") or "").strip()
        size = str(item.get("size") or "").strip() if item.get("size") is not None else ""

        enrich_input, condition_warnings = _build_enricher_input(item, seller_meta.get("seller_for_enricher"))
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
            "source_marketplace": MARKETPLACE_GRAILED,
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
            "source_offer_enabled": offer_meta.get("offer_enabled"),
            "source_minimum_offer": offer_meta.get("minimum_offer"),
            "source_offer_currency": offer_meta.get("offer_currency"),
            "source_seller_transactions": seller_meta.get("seller_transactions"),
            "source_seller_joined_year": seller_meta.get("seller_joined_year"),
            "grailed_parse_warnings": "; ".join(warnings) if warnings else None,
        }

        legacy_condition = used_details.condition.value.lower()
        availability = _availability_from_status(sale_status, inventory_status)

        return MarketplaceListing(
            marketplace_name=MARKETPLACE_GRAILED,
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
            raise GrailedResponseError("Grailed payload must be a JSON object")
        items = payload.get("items")
        if items is not None and not isinstance(items, list):
            raise GrailedResponseError("Grailed items must be a list when present")


def _parse_seller_metadata(block: Any) -> dict[str, Any]:
    """Validate Grailed seller block and extract Grailed-specific metadata."""
    result: dict[str, Any] = {
        "seller_for_enricher": None,
        "seller_transactions": None,
        "seller_joined_year": None,
        "seller_verified": None,
        "warnings": [],
    }
    if not isinstance(block, dict):
        return result

    seller_for_enricher = dict(block)
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

    joined_year = block.get("joined_year")
    if joined_year is not None:
        if isinstance(joined_year, bool) or not isinstance(joined_year, int) or not 1900 <= joined_year <= 2100:
            result["warnings"].append("invalid seller joined_year")
        else:
            result["seller_joined_year"] = joined_year

    verified = block.get("verified")
    if isinstance(verified, bool):
        result["seller_verified"] = verified
    elif verified is not None:
        result["warnings"].append("seller verified must be boolean or unknown")

    result["seller_for_enricher"] = seller_for_enricher
    return result


def _parse_offer_block(block: Any) -> dict[str, Any]:
    """Parse offer metadata without applying minimum offer to purchase price."""
    result: dict[str, Any] = {
        "offer_enabled": None,
        "minimum_offer": None,
        "offer_currency": None,
        "warnings": [],
    }
    if not isinstance(block, dict):
        return result

    enabled = block.get("enabled")
    if isinstance(enabled, bool):
        result["offer_enabled"] = enabled
    elif enabled is not None:
        result["warnings"].append("offer enabled must be boolean or unknown")

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
        result["offer_currency"] = str(currency).strip().upper() or None

    return result


def _should_include_item(
    sale_status: GrailedSaleStatus,
    inventory_status: GrailedInventoryStatus,
    *,
    include_sold: bool,
    include_reserved: bool,
    include_unavailable: bool,
) -> bool:
    if sale_status == GrailedSaleStatus.SOLD and not include_sold:
        return False
    if sale_status == GrailedSaleStatus.RESERVED and not include_reserved:
        return False
    if sale_status in {
        GrailedSaleStatus.INACTIVE,
        GrailedSaleStatus.REMOVED,
    } and not include_unavailable:
        return False

    if inventory_status == GrailedInventoryStatus.SOLD and not include_sold:
        return False
    if inventory_status == GrailedInventoryStatus.RESERVED and not include_reserved:
        return False
    if inventory_status == GrailedInventoryStatus.UNAVAILABLE and not include_unavailable:
        return False

    if sale_status in {
        GrailedSaleStatus.ACTIVE,
        GrailedSaleStatus.UNKNOWN,
    } and inventory_status in {
        GrailedInventoryStatus.IN_STOCK,
        GrailedInventoryStatus.UNKNOWN,
    }:
        return True

    if include_sold and (
        sale_status == GrailedSaleStatus.SOLD
        or inventory_status == GrailedInventoryStatus.SOLD
    ):
        return True
    if include_reserved and (
        sale_status == GrailedSaleStatus.RESERVED
        or inventory_status == GrailedInventoryStatus.RESERVED
    ):
        return True
    if include_unavailable and (
        sale_status in {GrailedSaleStatus.INACTIVE, GrailedSaleStatus.REMOVED}
        or inventory_status == GrailedInventoryStatus.UNAVAILABLE
    ):
        return True

    return False


def _inventory_sale_warnings(
    sale_status: GrailedSaleStatus,
    inventory_status: GrailedInventoryStatus,
) -> list[str]:
    warnings: list[str] = []
    if sale_status == GrailedSaleStatus.ACTIVE and inventory_status in {
        GrailedInventoryStatus.SOLD,
        GrailedInventoryStatus.UNAVAILABLE,
    }:
        warnings.append(
            f"sale_status {sale_status.value} conflicts with inventory {inventory_status.value}"
        )
    if sale_status == GrailedSaleStatus.SOLD and inventory_status == GrailedInventoryStatus.IN_STOCK:
        warnings.append(
            f"sale_status {sale_status.value} conflicts with inventory {inventory_status.value}"
        )
    return warnings


def _parse_inventory_status(block: Any) -> GrailedInventoryStatus:
    if not isinstance(block, dict):
        return GrailedInventoryStatus.UNKNOWN
    return GrailedInventoryStatus.from_value(block.get("status"))


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
        elif amount_raw is not None:
            result["discount_amount"] = None

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
    sale_status: GrailedSaleStatus,
    inventory_status: GrailedInventoryStatus,
) -> str:
    if sale_status == GrailedSaleStatus.SOLD or inventory_status == GrailedInventoryStatus.SOLD:
        return "sold"
    if sale_status == GrailedSaleStatus.RESERVED or inventory_status == GrailedInventoryStatus.RESERVED:
        return "reserved"
    if inventory_status == GrailedInventoryStatus.UNAVAILABLE:
        return "unavailable"
    if sale_status in {GrailedSaleStatus.INACTIVE, GrailedSaleStatus.REMOVED}:
        return "ended"
    if inventory_status == GrailedInventoryStatus.IN_STOCK:
        return "in_stock"
    return "unknown"


def _build_enricher_input(
    item: dict[str, Any],
    seller_override: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[str]]:
    """Build enricher input with Grailed condition preprocessing."""
    warnings: list[str] = []
    result = dict(item)
    if seller_override is not None:
        result["seller"] = seller_override

    condition_block = item.get("condition")
    if isinstance(condition_block, dict):
        raw = str(condition_block.get("raw") or "").strip()
        preprocessed, cond_warnings = preprocess_grailed_condition(raw)
        warnings.extend(cond_warnings)
        result["condition"] = {
            "raw": raw,
            "description": condition_block.get("description"),
            "normalized": condition_block.get("normalized"),
        }
        if preprocessed and not condition_block.get("normalized"):
            result["condition"]["raw"] = preprocessed
    elif isinstance(condition_block, str):
        preprocessed, cond_warnings = preprocess_grailed_condition(condition_block)
        warnings.extend(cond_warnings)
        result["condition"] = preprocessed or condition_block
    return result, warnings


def preprocess_grailed_condition(raw: str | None) -> tuple[str, list[str]]:
    """
    Preprocess Grailed condition strings before Phase 8 normalization.

    Does not upgrade ambiguous wear terms or conflate tags with condition grade.
    """
    warnings: list[str] = []
    if raw is None or not str(raw).strip():
        return "", warnings

    text = unicodedata.normalize("NFKC", str(raw).strip().lower())
    text = re.sub(r"\s+", " ", text)

    mappings = (
        (r"^new\s*/\s*never\s*worn$|^never\s*worn$", "never worn"),
        (r"^new\s*with\s*tags$", "new with tags"),
        (r"^new\s*without\s*tags$", "new without tags"),
        (r"^gently\s*used$", "gently used"),
        (r"^used$", "used"),
        (r"^well\s*worn$", "well worn"),
        (r"^heavily\s*worn$", "heavily worn"),
        (r"^vintage$", "vintage"),
        (r"^distressed$", "distressed"),
        (r"^as\s*is$", "as is"),
        (r"^damaged$", "damaged"),
        (r"^for\s*parts$", "for parts"),
        (r"^記載なし$", ""),
    )
    for pattern, replacement in mappings:
        if re.search(pattern, text):
            if replacement == "new with tags":
                warnings.append("new with tags describes tags; not conflated with accessories")
            if replacement == "new without tags":
                warnings.append("new without tags does not assert unused guarantee")
            if replacement == "gently used":
                warnings.append("gently used normalized conservatively")
            if replacement == "used":
                warnings.append("used alone does not imply good condition grade")
            if replacement == "vintage":
                warnings.append("vintage indicates age; not upgraded to good condition")
            if replacement == "distressed":
                warnings.append("distressed may be design or damage; requires caution")
            if replacement == "as is":
                warnings.append("as is condition requires buyer caution")
            if replacement == "damaged":
                warnings.append("damaged condition normalized conservatively")
            if replacement == "for parts":
                warnings.append("for parts indicates lowest usable condition")
            return replacement, warnings

    return text, warnings


def warn_minimum_offer_above_price(
    minimum_offer: float | None,
    current_price: Decimal,
) -> str | None:
    """Return warning when minimum offer exceeds current listing price."""
    if minimum_offer is None:
        return None
    if minimum_offer > float(current_price):
        return "minimum_offer exceeds current price"
    return None
