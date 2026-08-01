"""Manual and CSV candidate parsing."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from marketplace.acquisition_workspace.models import ParsedCandidate, SourceType


@dataclass
class ManualInputResult:
    candidates: list[ParsedCandidate] = field(default_factory=list)
    skipped_rows: int = 0
    errors: list[str] = field(default_factory=list)


MAX_MANUAL_ROWS = 10


def parse_manual_rows(rows: list[dict[str, str]]) -> ManualInputResult:
    result = ManualInputResult()
    for index, row in enumerate(rows[:MAX_MANUAL_ROWS], start=1):
        title = row.get("title", "").strip()
        price_raw = row.get("price", "").strip()
        currency = row.get("currency", "USD").strip().upper() or "USD"
        url = row.get("url", "").strip()
        source = row.get("source", "Manual").strip() or "Manual"
        condition = row.get("condition", "").strip()
        if not title and not price_raw and not url:
            continue
        if not title or not price_raw or not url:
            result.skipped_rows += 1
            result.errors.append(f"row {index}: title, price, and URL are required")
            continue
        try:
            from marketplace.acquisition_workspace.normalization import normalize_price

            price = normalize_price(price_raw)
        except Exception:
            result.skipped_rows += 1
            result.errors.append(f"row {index}: invalid price")
            continue
        result.candidates.append(
            ParsedCandidate(
                title=title,
                brand=row.get("brand", "").strip(),
                category=row.get("category", "Wallet").strip() or "Wallet",
                condition=condition,
                purchase_price=price,
                currency=currency,
                purchase_url=url,
                source_name=source,
                external_id=row.get("external_id", "").strip(),
                image_url=row.get("image_url", "").strip(),
                raw_description=row.get("description", "").strip()[:500],
                parser_strategy=SourceType.MANUAL.value,
            )
        )
    return result


def read_acquisition_csv(path: Path | str) -> tuple[list[dict[str, str]], list[str]]:
    csv_path = Path(path)
    errors: list[str] = []
    for encoding in ("utf-8-sig", "utf-8", "cp932"):
        try:
            with csv_path.open("r", encoding=encoding, newline="") as handle:
                reader = csv.reader(handle)
                all_rows = [row for row in reader if any(cell.strip() for cell in row)]
            break
        except UnicodeDecodeError:
            all_rows = []
            continue
    else:
        return [], ["unable to decode CSV with UTF-8 or CP932"]

    if not all_rows:
        return [], errors
    headers = [cell.strip().lower() for cell in all_rows[0]]
    if "title" not in headers:
        headers = [
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
            "image_url",
            "external_id",
            "description",
        ]
        data_rows = all_rows
    else:
        data_rows = all_rows[1:]

    rows: list[dict[str, str]] = []
    for line_number, values in enumerate(data_rows, start=1):
        mapped = {headers[i]: values[i].strip() for i in range(min(len(headers), len(values))) if values[i].strip()}
        if not mapped:
            continue
        if not mapped.get("purchase_url") and mapped.get("url"):
            mapped["purchase_url"] = mapped["url"]
        if not mapped.get("source") and mapped.get("market_name"):
            mapped["source"] = mapped["market_name"]
        if not mapped.get("purchase_price") and mapped.get("price"):
            mapped["purchase_price"] = mapped["price"]
        rows.append(mapped)
    return rows, errors


def csv_rows_to_parsed(rows: list[dict[str, str]]) -> tuple[list[ParsedCandidate], list[str], int]:
    parsed: list[ParsedCandidate] = []
    errors: list[str] = []
    skipped = 0
    for line_number, row in enumerate(rows, start=1):
        title = row.get("title", "").strip()
        price_raw = row.get("purchase_price", row.get("price", "")).strip()
        currency = row.get("currency", "USD").strip().upper() or "USD"
        url = row.get("purchase_url", row.get("url", "")).strip()
        if not title:
            skipped += 1
            errors.append(f"line {line_number}: missing title")
            continue
        if not price_raw:
            skipped += 1
            errors.append(f"line {line_number}: missing purchase_price")
            continue
        if not url:
            skipped += 1
            errors.append(f"line {line_number}: missing purchase_url")
            continue
        try:
            from marketplace.acquisition_workspace.normalization import normalize_price

            price = normalize_price(price_raw)
        except Exception:
            skipped += 1
            errors.append(f"line {line_number}: invalid purchase_price")
            continue
        warnings: list[str] = []
        if not row.get("brand", "").strip():
            warnings.append("brand not provided")
        parsed.append(
            ParsedCandidate(
                title=title,
                brand=row.get("brand", "").strip(),
                category=row.get("category", "Wallet").strip() or "Wallet",
                condition=row.get("condition", "").strip(),
                purchase_price=price,
                currency=currency,
                purchase_url=url,
                source_name=row.get("source", "CSV").strip() or "CSV",
                external_id=row.get("external_id", "").strip(),
                image_url=row.get("image_url", "").strip(),
                raw_description=row.get("description", "").strip()[:500],
                parser_strategy=SourceType.CSV.value,
                warnings=tuple(warnings),
            )
        )
    return parsed, errors, skipped
