"""Repository for saved opportunity records."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.storage.database import connect, resolve_database_path
from app.storage.models import OpportunityRecord, OpportunityStatus


class OpportunityRepository:
    """SQLite-backed CRUD repository for opportunity records."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        self._database_path = resolve_database_path(database_path)

    @property
    def database_path(self) -> Path:
        return self._database_path

    def save(self, record: OpportunityRecord) -> OpportunityRecord:
        """Insert one opportunity record."""
        now = datetime.now(tz=UTC)
        created_at = record.created_at if record.created_at.tzinfo else record.created_at.replace(tzinfo=UTC)
        updated_at = record.updated_at if record.updated_at.tzinfo else record.updated_at.replace(tzinfo=UTC)
        if record.id is None:
            created_at = now
            updated_at = now
        with connect(self._database_path) as connection:
            if record.id is None:
                cursor = connection.execute(
                    """
                    INSERT INTO opportunities (
                        product_name, brand, category,
                        purchase_source, purchase_url, purchase_price,
                        selling_market, selling_url, selling_price,
                        estimated_profit, profit_margin,
                        demand_score, turnover_score, arbitrage_score,
                        decision, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    _record_to_params(record, created_at=created_at, updated_at=updated_at),
                )
                record_id = int(cursor.lastrowid)
            else:
                connection.execute(
                    """
                    UPDATE opportunities SET
                        product_name = ?, brand = ?, category = ?,
                        purchase_source = ?, purchase_url = ?, purchase_price = ?,
                        selling_market = ?, selling_url = ?, selling_price = ?,
                        estimated_profit = ?, profit_margin = ?,
                        demand_score = ?, turnover_score = ?, arbitrage_score = ?,
                        decision = ?, status = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        record.product_name,
                        record.brand,
                        record.category,
                        record.purchase_source,
                        record.purchase_url,
                        record.purchase_price,
                        record.selling_market,
                        record.selling_url,
                        record.selling_price,
                        record.estimated_profit,
                        record.profit_margin,
                        record.demand_score,
                        record.turnover_score,
                        record.arbitrage_score,
                        record.decision,
                        record.status.value,
                        updated_at.isoformat(),
                        record.id,
                    ),
                )
                record_id = record.id
            connection.commit()
        saved = self.get_by_id(record_id)
        assert saved is not None
        return saved

    def get_by_id(self, record_id: int) -> OpportunityRecord | None:
        """Return one opportunity by primary key."""
        with connect(self._database_path) as connection:
            row = connection.execute(
                "SELECT * FROM opportunities WHERE id = ?",
                (record_id,),
            ).fetchone()
        if row is None:
            return None
        return _row_to_record(row)

    def list_all(self) -> list[OpportunityRecord]:
        """Return all saved opportunities ordered by newest first."""
        with connect(self._database_path) as connection:
            rows = connection.execute(
                "SELECT * FROM opportunities ORDER BY created_at DESC, id DESC",
            ).fetchall()
        return [_row_to_record(row) for row in rows]

    def update_status(self, record_id: int, status: OpportunityStatus) -> OpportunityRecord | None:
        """Update workflow status for one opportunity."""
        existing = self.get_by_id(record_id)
        if existing is None:
            return None
        updated = OpportunityRecord(
            id=existing.id,
            product_name=existing.product_name,
            brand=existing.brand,
            category=existing.category,
            purchase_source=existing.purchase_source,
            purchase_url=existing.purchase_url,
            purchase_price=existing.purchase_price,
            selling_market=existing.selling_market,
            selling_url=existing.selling_url,
            selling_price=existing.selling_price,
            estimated_profit=existing.estimated_profit,
            profit_margin=existing.profit_margin,
            demand_score=existing.demand_score,
            turnover_score=existing.turnover_score,
            arbitrage_score=existing.arbitrage_score,
            decision=existing.decision,
            status=status,
            created_at=existing.created_at,
            updated_at=datetime.now(tz=UTC),
        )
        return self.save(updated)

    def delete(self, record_id: int) -> bool:
        """Delete one opportunity record."""
        with connect(self._database_path) as connection:
            cursor = connection.execute(
                "DELETE FROM opportunities WHERE id = ?",
                (record_id,),
            )
            connection.commit()
            return cursor.rowcount > 0

    def find_by_purchase_url(self, purchase_url: str) -> OpportunityRecord | None:
        """Return the newest saved record for one purchase URL."""
        normalized = purchase_url.strip()
        if not normalized:
            return None
        with connect(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT * FROM opportunities
                WHERE purchase_url = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (normalized,),
            ).fetchone()
        if row is None:
            return None
        return _row_to_record(row)


def _record_to_params(
    record: OpportunityRecord,
    *,
    created_at: datetime,
    updated_at: datetime,
) -> tuple[object, ...]:
    return (
        record.product_name,
        record.brand,
        record.category,
        record.purchase_source,
        record.purchase_url,
        record.purchase_price,
        record.selling_market,
        record.selling_url,
        record.selling_price,
        record.estimated_profit,
        record.profit_margin,
        record.demand_score,
        record.turnover_score,
        record.arbitrage_score,
        record.decision,
        record.status.value,
        created_at.isoformat(),
        updated_at.isoformat(),
    )


def _row_to_record(row: object) -> OpportunityRecord:
    data = dict(row)  # type: ignore[arg-type]
    return OpportunityRecord(
        id=int(data["id"]),
        product_name=str(data["product_name"]),
        brand=str(data["brand"]),
        category=str(data["category"]),
        purchase_source=str(data["purchase_source"]),
        purchase_url=str(data["purchase_url"]),
        purchase_price=float(data["purchase_price"]),
        selling_market=str(data["selling_market"]),
        selling_url=str(data["selling_url"]),
        selling_price=float(data["selling_price"]),
        estimated_profit=float(data["estimated_profit"]),
        profit_margin=float(data["profit_margin"]),
        demand_score=float(data["demand_score"]),
        turnover_score=float(data["turnover_score"]),
        arbitrage_score=float(data["arbitrage_score"]),
        decision=str(data["decision"]),
        status=OpportunityStatus(str(data["status"])),
        created_at=datetime.fromisoformat(str(data["created_at"])),
        updated_at=datetime.fromisoformat(str(data["updated_at"])),
    )
