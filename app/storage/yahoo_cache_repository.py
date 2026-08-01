"""SQLite repository for Yahoo search cache."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.storage.database import connect
from marketplace.browser_acquisition.yahoo_search_cache import (
    YahooCacheEntry,
    deserialize_diagnostics,
    deserialize_samples,
    is_cache_valid,
    normalize_query,
    serialize_diagnostics,
    serialize_samples,
)


class YahooSearchCacheRepository:
    """Persist and retrieve Yahoo search cache entries."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        self._database_path = database_path

    def get(self, query: str) -> YahooCacheEntry | None:
        normalized = normalize_query(query)
        with connect(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT normalized_query, source, retrieved_at, expires_at, acquisition_status,
                       raw_sample_count, samples_json, diagnostics_json
                FROM yahoo_search_cache
                WHERE normalized_query = ?
                """,
                (normalized,),
            ).fetchone()
        if row is None:
            return None
        if not is_cache_valid(row["expires_at"]):
            self.delete(normalized)
            return None
        return YahooCacheEntry(
            normalized_query=row["normalized_query"],
            source=row["source"],
            retrieved_at=row["retrieved_at"],
            expires_at=row["expires_at"],
            acquisition_status=row["acquisition_status"],
            raw_sample_count=int(row["raw_sample_count"]),
            samples=tuple(deserialize_samples(row["samples_json"])),
            diagnostics=tuple(deserialize_diagnostics(row["diagnostics_json"])),
        )

    def save(self, entry: YahooCacheEntry) -> None:
        now = datetime.now(tz=UTC).isoformat()
        with connect(self._database_path) as connection:
            connection.execute(
                """
                INSERT INTO yahoo_search_cache (
                    normalized_query, source, retrieved_at, expires_at, acquisition_status,
                    raw_sample_count, samples_json, diagnostics_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(normalized_query) DO UPDATE SET
                    source=excluded.source,
                    retrieved_at=excluded.retrieved_at,
                    expires_at=excluded.expires_at,
                    acquisition_status=excluded.acquisition_status,
                    raw_sample_count=excluded.raw_sample_count,
                    samples_json=excluded.samples_json,
                    diagnostics_json=excluded.diagnostics_json,
                    created_at=excluded.created_at
                """,
                (
                    entry.normalized_query,
                    entry.source,
                    entry.retrieved_at,
                    entry.expires_at,
                    entry.acquisition_status,
                    entry.raw_sample_count,
                    serialize_samples(list(entry.samples)),
                    serialize_diagnostics(list(entry.diagnostics)),
                    now,
                ),
            )
            connection.commit()

    def delete(self, normalized_query: str) -> None:
        with connect(self._database_path) as connection:
            connection.execute(
                "DELETE FROM yahoo_search_cache WHERE normalized_query = ?",
                (normalize_query(normalized_query),),
            )
            connection.commit()
