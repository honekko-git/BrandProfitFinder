"""Repository for imported market listing records."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.storage.database import connect, resolve_database_path
from app.storage.market_listing_models import MarketListingRecord


class MarketListingRepository:
    """SQLite-backed CRUD repository for imported market listings."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        self._database_path = resolve_database_path(database_path)

    @property
    def database_path(self) -> Path:
        return self._database_path

    def save(self, record: MarketListingRecord) -> MarketListingRecord:
        """Insert or update one market listing record."""
        created_at = record.created_at if record.created_at.tzinfo else record.created_at.replace(tzinfo=UTC)
        with connect(self._database_path) as connection:
            if record.id is None:
                cursor = connection.execute(
                    """
                    INSERT INTO market_listings (
                        title, brand, category, condition, price, currency,
                        market_name, url, external_key, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.title,
                        record.brand,
                        record.category,
                        record.condition,
                        record.price,
                        record.currency,
                        record.market_name,
                        record.url,
                        record.external_key,
                        created_at.isoformat(),
                    ),
                )
                record_id = int(cursor.lastrowid)
            else:
                connection.execute(
                    """
                    UPDATE market_listings SET
                        title = ?, brand = ?, category = ?, condition = ?,
                        price = ?, currency = ?, market_name = ?, url = ?,
                        external_key = ?
                    WHERE id = ?
                    """,
                    (
                        record.title,
                        record.brand,
                        record.category,
                        record.condition,
                        record.price,
                        record.currency,
                        record.market_name,
                        record.url,
                        record.external_key,
                        record.id,
                    ),
                )
                record_id = record.id
            connection.commit()
        saved = self.get_by_id(record_id)
        assert saved is not None
        return saved

    def get_by_id(self, record_id: int) -> MarketListingRecord | None:
        """Return one listing by primary key."""
        with connect(self._database_path) as connection:
            row = connection.execute(
                "SELECT * FROM market_listings WHERE id = ?",
                (record_id,),
            ).fetchone()
        if row is None:
            return None
        return _row_to_record(row)

    def list_all(self) -> list[MarketListingRecord]:
        """Return all imported listings ordered by newest first."""
        with connect(self._database_path) as connection:
            rows = connection.execute(
                "SELECT * FROM market_listings ORDER BY created_at DESC, id DESC",
            ).fetchall()
        return [_row_to_record(row) for row in rows]

    def search(self, query: str) -> list[MarketListingRecord]:
        """Search imported listings by title, brand, or market name."""
        normalized = f"%{query.strip().lower()}%"
        with connect(self._database_path) as connection:
            rows = connection.execute(
                """
                SELECT * FROM market_listings
                WHERE lower(title) LIKE ?
                   OR lower(brand) LIKE ?
                   OR lower(market_name) LIKE ?
                ORDER BY created_at DESC, id DESC
                """,
                (normalized, normalized, normalized),
            ).fetchall()
        return [_row_to_record(row) for row in rows]

    def delete(self, record_id: int) -> bool:
        """Delete one imported listing."""
        with connect(self._database_path) as connection:
            cursor = connection.execute(
                "DELETE FROM market_listings WHERE id = ?",
                (record_id,),
            )
            connection.commit()
            return cursor.rowcount > 0


def _row_to_record(row: object) -> MarketListingRecord:
    data = dict(row)  # type: ignore[arg-type]
    return MarketListingRecord(
        id=int(data["id"]),
        title=str(data["title"]),
        brand=str(data["brand"]),
        category=str(data["category"]),
        condition=str(data["condition"]),
        price=float(data["price"]),
        currency=str(data["currency"]),
        market_name=str(data["market_name"]),
        url=str(data["url"]),
        external_key=str(data["external_key"]),
        created_at=datetime.fromisoformat(str(data["created_at"])),
    )
