"""SQLite persistence for controlled live acquisition evidence."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from app.storage.database import connect, resolve_database_path
from marketplace.browser_acquisition.models import ControlledLiveVerificationResult


CREATE_LIVE_ACQUISITION_EVIDENCE_TABLE = """
CREATE TABLE IF NOT EXISTS live_acquisition_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    search_query TEXT NOT NULL,
    listing_url TEXT NOT NULL,
    displayed_price REAL NOT NULL,
    currency TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    acquisition_status TEXT NOT NULL,
    matching_summary TEXT NOT NULL,
    profit_result TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""


@dataclass(frozen=True, slots=True)
class LiveAcquisitionEvidenceRecord:
    """One stored controlled live acquisition evidence row."""

    id: int | None
    source: str
    search_query: str
    listing_url: str
    displayed_price: float
    currency: str
    retrieved_at: str
    acquisition_status: str
    matching_summary: str
    profit_result: str
    created_at: str


class LiveAcquisitionEvidenceRepository:
    """Persist minimal controlled live acquisition evidence."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        self._database_path = resolve_database_path(database_path)

    def save_result(self, result: ControlledLiveVerificationResult) -> LiveAcquisitionEvidenceRecord:
        """Save one controlled live verification result."""
        matching_summary = json.dumps(
            {
                "yahoo_search_terms": result.yahoo_search_terms,
                "yahoo_sold_samples": result.yahoo_sold_samples,
                "yahoo_matched_samples": result.yahoo_matched_samples,
                "matching_score": result.matching_score,
                "matching_reliability": result.matching_reliability,
                "blocking_reason": result.blocking_reason,
            },
            ensure_ascii=False,
        )
        profit_payload = json.dumps(
            {
                "estimated_profit": str(result.estimated_profit),
                "profit_margin": str(result.profit_margin),
                "roi": str(result.roi),
                "decision": result.decision,
                "median_selling_price_jpy": str(result.median_selling_price_jpy),
                "data_status": result.data_status,
                "verification_complete": result.verification_complete,
            },
            ensure_ascii=False,
        )
        created_at = datetime.now(tz=UTC).isoformat()
        with connect(self._database_path) as connection:
            self._ensure_schema(connection)
            cursor = connection.execute(
                """
                INSERT INTO live_acquisition_evidence (
                    source, search_query, listing_url, displayed_price, currency,
                    retrieved_at, acquisition_status, matching_summary, profit_result, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "Fashionphile",
                    result.yahoo_search_terms,
                    result.fashionphile_url,
                    float(result.purchase_price),
                    result.purchase_currency,
                    result.retrieved_at,
                    result.acquisition_status,
                    matching_summary,
                    profit_payload,
                    created_at,
                ),
            )
            connection.commit()
            record_id = int(cursor.lastrowid)
        return LiveAcquisitionEvidenceRecord(
            id=record_id,
            source="Fashionphile",
            search_query=result.yahoo_search_terms,
            listing_url=result.fashionphile_url,
            displayed_price=float(result.purchase_price),
            currency=result.purchase_currency,
            retrieved_at=result.retrieved_at,
            acquisition_status=result.acquisition_status,
            matching_summary=matching_summary,
            profit_result=profit_payload,
            created_at=created_at,
        )

    def list_recent(self, limit: int = 20) -> list[LiveAcquisitionEvidenceRecord]:
        with connect(self._database_path) as connection:
            self._ensure_schema(connection)
            rows = connection.execute(
                """
                SELECT * FROM live_acquisition_evidence
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_row_to_record(row) for row in rows]

    def _ensure_schema(self, connection: sqlite3.Connection) -> None:
        connection.execute(CREATE_LIVE_ACQUISITION_EVIDENCE_TABLE)


def _row_to_record(row: sqlite3.Row) -> LiveAcquisitionEvidenceRecord:
    return LiveAcquisitionEvidenceRecord(
        id=int(row["id"]),
        source=str(row["source"]),
        search_query=str(row["search_query"]),
        listing_url=str(row["listing_url"]),
        displayed_price=float(row["displayed_price"]),
        currency=str(row["currency"]),
        retrieved_at=str(row["retrieved_at"]),
        acquisition_status=str(row["acquisition_status"]),
        matching_summary=str(row["matching_summary"]),
        profit_result=str(row["profit_result"]),
        created_at=str(row["created_at"]),
    )
