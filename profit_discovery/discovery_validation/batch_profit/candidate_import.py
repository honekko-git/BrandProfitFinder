"""Candidate import helpers for batch profit discovery."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4

from marketplace.browser_acquisition.luxury_material import detect_luxury_material
from marketplace.browser_acquisition.product_subtype import detect_wallet_subtype
from marketplace.connectors.models import MarketListing
from profit_discovery.discovery_validation.batch_profit.condition import detect_condition
from profit_discovery.discovery_validation.batch_profit.models import BatchProfitCandidate
from profit_discovery.discovery_validation.real_profit_config import resolve_usd_jpy_exchange_rate

BATCH_CSV_FIELDS = (
    "title",
    "brand",
    "category",
    "subtype",
    "material",
    "condition",
    "purchase_price",
    "currency",
    "purchase_url",
    "source",
)

REQUIRED_FIELDS = ("title", "brand", "category", "purchase_price", "currency", "purchase_url")


@dataclass
class BatchImportResult:
    """Result from batch candidate import."""

    candidates: list[BatchProfitCandidate] = field(default_factory=list)
    skipped_rows: int = 0
    errors: list[str] = field(default_factory=list)


def load_batch_candidates_from_csv(path: Path | str, *, limit: int = 20) -> BatchImportResult:
    """Load batch candidates from CSV with per-row validation."""
    csv_path = Path(path)
    rows = _read_csv_rows(csv_path)
    return rows_to_candidates(rows, limit=limit)


def rows_to_candidates(rows: list[dict[str, str]], *, limit: int = 20) -> BatchImportResult:
    """Convert validated CSV rows into batch candidates with dedupe."""
    result = BatchImportResult()
    seen_urls: set[str] = set()
    seen_signatures: set[str] = set()
    seen_ids: set[str] = set()

    for line_number, raw_row in enumerate(rows, start=1):
        if len(result.candidates) >= limit:
            break
        row = _normalize_batch_row(raw_row)
        ok, errors = _validate_batch_row(row)
        if not ok:
            result.skipped_rows += 1
            result.errors.append(f"line {line_number}: {'; '.join(errors)}")
            continue

        external_id = row.get("external_id", "").strip()
        purchase_url = row["purchase_url"].strip()
        signature = _candidate_signature(row)
        if external_id and external_id in seen_ids:
            result.skipped_rows += 1
            result.errors.append(f"line {line_number}: duplicate external_id")
            continue
        if purchase_url and purchase_url in seen_urls:
            result.skipped_rows += 1
            result.errors.append(f"line {line_number}: duplicate purchase_url")
            continue
        if signature in seen_signatures:
            result.skipped_rows += 1
            result.errors.append(f"line {line_number}: duplicate title/price/currency")
            continue

        candidate = _row_to_candidate(row)
        result.candidates.append(candidate)
        if external_id:
            seen_ids.add(external_id)
        if purchase_url:
            seen_urls.add(purchase_url)
        seen_signatures.add(signature)

    return result


def candidates_from_market_listings(
    listings: list[MarketListing],
    *,
    limit: int = 20,
) -> BatchImportResult:
    """Convert persisted market listings into batch candidates."""
    rows: list[dict[str, str]] = []
    for listing in listings[:limit]:
        rows.append(
            {
                "title": listing.title,
                "brand": listing.brand,
                "category": listing.category,
                "condition": listing.condition,
                "purchase_price": str(listing.price),
                "currency": listing.currency,
                "purchase_url": listing.url,
                "source": listing.market_name,
                "external_id": listing.id,
            }
        )
    return rows_to_candidates(rows, limit=limit)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        all_rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not all_rows:
        return []
    headers = [cell.strip().lower() for cell in all_rows[0]]
    if "title" in headers and "brand" in headers:
        data_rows = all_rows[1:]
    else:
        headers = list(BATCH_CSV_FIELDS)
        data_rows = all_rows
    rows: list[dict[str, str]] = []
    for row in data_rows:
        mapped = {headers[index]: value.strip() for index, value in enumerate(row) if index < len(headers)}
        if mapped:
            rows.append(mapped)
    return rows


def _normalize_batch_row(row: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    aliases = {
        "purchase_price": ("purchase_price", "price"),
        "purchase_url": ("purchase_url", "url"),
        "source": ("source", "market_name"),
    }
    for key, value in row.items():
        normalized[key.strip().lower()] = str(value).strip()
    for canonical, options in aliases.items():
        if canonical not in normalized:
            for option in options:
                if option in normalized:
                    normalized[canonical] = normalized[option]
                    break
    return normalized


def _validate_batch_row(row: dict[str, str]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    for field_name in REQUIRED_FIELDS:
        if not row.get(field_name, "").strip():
            errors.append(f"missing required field: {field_name}")
    try:
        price = Decimal(row.get("purchase_price", "0").replace(",", ""))
        if price <= 0:
            errors.append("purchase_price must be greater than zero")
    except InvalidOperation:
        errors.append("invalid purchase_price")
    return len(errors) == 0, errors


def _row_to_candidate(row: dict[str, str]) -> BatchProfitCandidate:
    title = row["title"]
    subtype_override = row.get("subtype", "").strip()
    material_override = row.get("material", "").strip()
    condition = row.get("condition", "Used").strip() or "Used"
    currency = row.get("currency", "USD").strip().upper() or "USD"
    price = Decimal(row.get("purchase_price", "0").replace(",", ""))
    rate = Decimal(str(resolve_usd_jpy_exchange_rate()))
    purchase_jpy = price if currency == "JPY" else price * rate
    detected_subtype = subtype_override or detect_wallet_subtype(title).value
    detected_material = material_override or detect_luxury_material(title).value
    detected_condition = detect_condition(f"{title} {condition}").value
    candidate_id = row.get("external_id", "").strip() or f"batch-{uuid4().hex[:12]}"
    return BatchProfitCandidate(
        candidate_id=candidate_id,
        title=title,
        brand=row["brand"],
        category=row.get("category", "Wallet"),
        detected_subtype=detected_subtype,
        detected_material=detected_material,
        condition=detected_condition,
        purchase_price=price,
        currency=currency,
        purchase_price_jpy=purchase_jpy,
        purchase_url=row["purchase_url"],
        purchase_source=row.get("source", "Import") or "Import",
        import_status="OK",
        subtype_override=subtype_override,
        material_override=material_override,
    )


def _candidate_signature(row: dict[str, str]) -> str:
    title = re.sub(r"\s+", " ", row.get("title", "").strip().lower())
    price = row.get("purchase_price", "").replace(",", "").strip()
    currency = row.get("currency", "").strip().upper()
    return f"{title}|{price}|{currency}"
