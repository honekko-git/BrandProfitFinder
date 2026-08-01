"""CSV importer for market listing data."""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from marketplace.connectors.models import MarketListing
from marketplace.importers.validators import CSV_FIELD_NAMES, is_header_row, validate_row

logger = logging.getLogger(__name__)


@dataclass
class CSVImportResult:
    """Result from one CSV import operation."""

    listings: list[MarketListing] = field(default_factory=list)
    skipped_rows: int = 0
    errors: list[str] = field(default_factory=list)


class CSVImporter:
    """Load market listings from a CSV file."""

    def __init__(self, *, path: Path | str | None = None) -> None:
        self._path = Path(path) if path is not None else None
        self._rows: list[dict[str, str]] = []
        self._errors: list[str] = []

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def rows(self) -> list[dict[str, str]]:
        return list(self._rows)

    @property
    def errors(self) -> list[str]:
        return list(self._errors)

    def load_csv(self, path: Path | str) -> list[dict[str, str]]:
        """Load raw rows from one CSV file."""
        self._path = Path(path)
        self._rows = []
        self._errors = []
        with self._path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            all_rows = [row for row in reader if any(cell.strip() for cell in row)]
        if not all_rows:
            return self._rows

        if is_header_row(all_rows[0]):
            headers = [cell.strip().lower() for cell in all_rows[0]]
            for line_number, row in enumerate(all_rows[1:], start=2):
                mapped = _map_row(headers, row)
                if mapped:
                    self._rows.append(mapped)
                else:
                    self._errors.append(f"line {line_number}: empty row")
        else:
            for line_number, row in enumerate(all_rows, start=1):
                mapped = _map_positional_row(row)
                if mapped:
                    self._rows.append(mapped)
                else:
                    self._errors.append(f"line {line_number}: empty row")
        return self._rows

    def validate_rows(self) -> list[dict[str, str]]:
        """Validate loaded rows and keep only valid entries."""
        valid_rows: list[dict[str, str]] = []
        for index, row in enumerate(self._rows, start=1):
            ok, errors = validate_row(row)
            if ok:
                valid_rows.append(row)
                continue
            message = f"row {index}: {'; '.join(errors)}"
            self._errors.append(message)
            logger.warning("Skipping invalid CSV row: %s", message)
        self._rows = valid_rows
        return self._rows

    def to_market_listings(self) -> CSVImportResult:
        """Convert validated rows into MarketListing objects."""
        created_at = datetime.now(tz=UTC)
        listings: list[MarketListing] = []
        skipped = 0
        for index, row in enumerate(self._rows, start=1):
            ok, errors = validate_row(row)
            if not ok:
                skipped += 1
                self._errors.extend(f"row {index}: {error}" for error in errors)
                continue
            listings.append(_row_to_market_listing(row, created_at=created_at))
        return CSVImportResult(
            listings=listings,
            skipped_rows=skipped,
            errors=list(self._errors),
        )


def _map_row(headers: list[str], values: list[str]) -> dict[str, str]:
    if not any(value.strip() for value in values):
        return {}
    mapped: dict[str, str] = {}
    for header, value in zip(headers, values, strict=False):
        mapped[header] = value.strip()
    return mapped


def _map_positional_row(values: list[str]) -> dict[str, str]:
    if not any(value.strip() for value in values):
        return {}
    mapped: dict[str, str] = {}
    for index, field_name in enumerate(CSV_FIELD_NAMES):
        if index < len(values):
            mapped[field_name] = values[index].strip()
    return mapped


def _row_to_market_listing(row: dict[str, str], *, created_at: datetime) -> MarketListing:
    listing_id = row.get("id", "").strip() or f"import-{uuid4().hex[:12]}"
    price = Decimal(str(row.get("price", "0")).replace(",", ""))
    return MarketListing(
        id=listing_id,
        title=row.get("title", "").strip(),
        brand=row.get("brand", "").strip(),
        category=row.get("category", "bag").strip() or "bag",
        condition=row.get("condition", "used").strip() or "used",
        price=price,
        currency=row.get("currency", "JPY").strip().upper() or "JPY",
        market_name=row.get("market_name", "").strip(),
        url=row.get("url", "").strip(),
        source_type="IMPORT",
        created_at=created_at,
    )
