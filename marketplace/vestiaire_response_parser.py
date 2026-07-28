"""
Vestiaire Collective internal standard response parser.

Parses BrandProfitFinder internal Vestiaire fixture JSON (not an official API format).
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any

from config.constants import CURRENCY_JPY, MARKETPLACE_VESTIAIRE
from marketplace.amazon_price_normalizer import parse_jpy_price
from marketplace.vestiaire_exceptions import VestiaireParseError, VestiaireResponseError
from models.marketplace_listing import MarketplaceListing
from used_luxury.enrichment import UsedItemEnricher

logger = logging.getLogger(__name__)


class VestiaireSaleStatus(str, Enum):
    """Listing sale status (distinct from item condition)."""

    ACTIVE = "ACTIVE"
    RESERVED = "RESERVED"
    SOLD = "SOLD"
    INACTIVE = "INACTIVE"
    REMOVED = "REMOVED"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_value(cls, value: Any) -> "VestiaireSaleStatus":
        if value is None:
            return cls.UNKNOWN
        text = str(value).strip().upper().replace("-", "_").replace(" ", "_")
        try:
            return cls(text)
        except ValueError:
            return cls.UNKNOWN


@dataclass
class VestiaireParseResult:
    """Result of parsing a Vestiaire search payload."""

    listings: list[MarketplaceListing] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rejected_count: int = 0


class VestiaireResponseParser:
    """Parse internal standard Vestiaire JSON into marketplace listings."""

    def __init__(self, enricher: UsedItemEnricher | None = None) -> None:
        self._enricher = enricher or UsedItemEnricher()

    def parse(
        self,
        payload: dict[str, object],
        *,
        source_query: str = "",
        include_sold: bool = False,
        include_inactive: bool = False,
        allow_unknown_currency: bool = False,
        default_currency: str = CURRENCY_JPY,
    ) -> VestiaireParseResult:
        """
        Parse Vestiaire internal standard JSON into listings.

        Args:
            payload: BrandProfitFinder internal Vestiaire standard JSON.
            source_query: Query label for listings.
            include_sold: Include SOLD listings when True.
            include_inactive: Include INACTIVE/REMOVED listings when True.
            allow_unknown_currency: Allow non-JPY without conversion when True.
            default_currency: Expected currency when not specified.

        Returns:
            Parse result with listings, warnings, and rejected count.
        """
        result = VestiaireParseResult()
        items = payload.get("items")
        if items is None:
            return result
        if not isinstance(items, list):
            raise VestiaireParseError("Vestiaire items must be a list when present")

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

            sale_status = VestiaireSaleStatus.from_value(item.get("sale_status"))
            if not _should_include_status(sale_status, include_sold, include_inactive):
                result.rejected_count += 1
                continue

            listing, item_warnings = self._parse_item(
                item,
                source_query=source_query,
                allow_unknown_currency=allow_unknown_currency,
                default_currency=default_currency,
                sale_status=sale_status,
            )
            if listing is None:
                result.rejected_count += 1
                result.warnings.extend(item_warnings)
                continue

            if listing_id:
                seen_ids.add(listing_id)
            result.listings.append(listing)
            result.warnings.extend(item_warnings)

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
        sale_status: VestiaireSaleStatus,
    ) -> tuple[MarketplaceListing | None, list[str]]:
        warnings: list[str] = []
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

        listing_url = str(item.get("url") or "").strip()
        image_url = str(item.get("image_url") or "").strip()
        model_number = str(item.get("model_number") or "").strip()
        brand = str(item.get("brand") or "").strip()
        color = str(item.get("color") or "").strip()
        size = str(item.get("size") or "").strip() if item.get("size") is not None else ""

        enrich_input = _build_enricher_input(item)
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

        parse_warnings = item.get("metadata", {}).get("parse_warnings") if isinstance(item.get("metadata"), dict) else None
        if isinstance(parse_warnings, list):
            warnings.extend(str(w) for w in parse_warnings)

        source_metadata: dict[str, Any] = {
            "source_marketplace": MARKETPLACE_VESTIAIRE,
            "source_listing_id": listing_id,
            "source_currency": currency,
            "source_shipping_known": not shipping_unknown,
            "source_sale_status": sale_status.value,
            "source_category": str(item.get("category") or "").strip() or None,
            "source_sub_category": str(item.get("sub_category") or "").strip() or None,
            "source_material": str(item.get("material") or "").strip() or None,
            "source_gender": str(item.get("gender") or "").strip() or None,
            "source_country": str(item.get("country_of_origin") or "").strip() or None,
            "source_listed_at": str(item.get("listed_at") or "").strip() or None,
            "source_color": color or None,
            "source_size": size or None,
            "vestiaire_parse_warnings": "; ".join(warnings) if warnings else None,
        }

        legacy_condition = used_details.condition.value.lower()
        availability = _availability_from_sale_status(sale_status)

        return MarketplaceListing(
            marketplace_name=MARKETPLACE_VESTIAIRE,
            listing_id=listing_id or title,
            title=title or listing_id,
            brand=brand,
            model_number=model_number,
            sku="",
            condition=legacy_condition,
            price_jpy=price_jpy,
            shipping_jpy=shipping_jpy,
            shipping_unknown=shipping_unknown,
            seller_name=str(item.get("seller_name") or used_details.seller_details.business_name or "").strip(),
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
            raise VestiaireResponseError("Vestiaire payload must be a JSON object")
        items = payload.get("items")
        if items is not None and not isinstance(items, list):
            raise VestiaireResponseError("Vestiaire items must be a list when present")


def _should_include_status(
    status: VestiaireSaleStatus,
    include_sold: bool,
    include_inactive: bool,
) -> bool:
    if status == VestiaireSaleStatus.ACTIVE:
        return True
    if status == VestiaireSaleStatus.RESERVED:
        return True
    if status == VestiaireSaleStatus.SOLD and include_sold:
        return True
    if status in {VestiaireSaleStatus.INACTIVE, VestiaireSaleStatus.REMOVED} and include_inactive:
        return True
    if status == VestiaireSaleStatus.UNKNOWN:
        return True
    return False


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

    known = block.get("known")
    if known is False:
        return None, True, []

    amount_raw = block.get("amount")
    if amount_raw is None:
        return None, True, []

    if isinstance(amount_raw, bool):
        return None, True, ["boolean shipping amount rejected"]

    amount = parse_jpy_price(amount_raw)
    if amount is None:
        return None, True, ["invalid shipping amount"]
    return amount, False, warnings


def _availability_from_sale_status(status: VestiaireSaleStatus) -> str:
    if status == VestiaireSaleStatus.ACTIVE:
        return "in_stock"
    if status == VestiaireSaleStatus.SOLD:
        return "sold"
    if status == VestiaireSaleStatus.RESERVED:
        return "reserved"
    if status in {VestiaireSaleStatus.INACTIVE, VestiaireSaleStatus.REMOVED}:
        return "ended"
    return "unknown"


def _build_enricher_input(item: dict[str, Any]) -> dict[str, Any]:
    """Build enricher input from Vestiaire item, preprocessing condition text."""
    result = dict(item)
    condition_block = item.get("condition")
    if isinstance(condition_block, dict):
        raw = str(condition_block.get("raw") or "").strip()
        preprocessed = preprocess_vestiaire_condition(raw)
        result["condition"] = {
            "raw": raw,
            "description": condition_block.get("description"),
            "normalized": condition_block.get("normalized"),
        }
        if preprocessed != raw:
            result["condition"] = {
                **result["condition"],
                "raw": preprocessed if not condition_block.get("normalized") else raw,
            }
    elif isinstance(condition_block, str):
        result["condition"] = preprocess_vestiaire_condition(condition_block)
    return result


def preprocess_vestiaire_condition(raw: str | None) -> str:
    """
    Preprocess Vestiaire-specific condition strings before Phase 8 normalization.

    Does not upgrade ambiguous terms to ranked grades.
    """
    if raw is None or not str(raw).strip():
        return ""
    text = unicodedata.normalize("NFKC", str(raw).strip().lower())
    text = re.sub(r"\s+", " ", text)

    mappings = (
        (r"^never worn$", "never worn"),
        (r"^never used$", "never used"),
        (r"very good condition", "very good"),
        (r"good condition", "good"),
        (r"fair condition", "fair"),
        (r"^vintage$", "vintage"),
        (r"^pre[- ]?owned$", "pre-owned"),
        (r"^damaged$", "damaged"),
        (r"^for parts$", "for parts"),
    )
    for pattern, replacement in mappings:
        if re.search(pattern, text):
            return replacement
    return text
