"""SQLite repository for acquisition workspace."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from app.storage.database import connect
from marketplace.acquisition_workspace.models import (
    AcquisitionCandidate,
    DataTruthSummary,
    DiscoveryMetadata,
    ImportEvent,
    WorkspaceBatch,
    validate_candidate_transparency,
)


class AcquisitionWorkspaceRepository:
    def __init__(self, database_path: Path | str | None = None) -> None:
        self._database_path = database_path

    def save_batch(self, batch: WorkspaceBatch) -> None:
        with connect(self._database_path) as connection:
            connection.execute(
                """
                INSERT INTO acquisition_workspace_batches (
                    workspace_batch_id, name, source_type, created_at, updated_at,
                    total_rows, accepted_count, warning_count, rejected_count,
                    duplicate_count, selected_count, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch.workspace_batch_id,
                    batch.name,
                    batch.source_type,
                    batch.created_at,
                    batch.updated_at,
                    batch.total_rows,
                    batch.accepted_count,
                    batch.warning_count,
                    batch.rejected_count,
                    batch.duplicate_count,
                    batch.selected_count,
                    batch.status,
                ),
            )
            connection.commit()

    def update_batch(self, batch: WorkspaceBatch) -> None:
        with connect(self._database_path) as connection:
            connection.execute(
                """
                UPDATE acquisition_workspace_batches SET
                    name=?, source_type=?, updated_at=?, total_rows=?, accepted_count=?,
                    warning_count=?, rejected_count=?, duplicate_count=?, selected_count=?, status=?
                WHERE workspace_batch_id=?
                """,
                (
                    batch.name,
                    batch.source_type,
                    batch.updated_at,
                    batch.total_rows,
                    batch.accepted_count,
                    batch.warning_count,
                    batch.rejected_count,
                    batch.duplicate_count,
                    batch.selected_count,
                    batch.status,
                    batch.workspace_batch_id,
                ),
            )
            connection.commit()

    def list_batches(self, *, limit: int = 20) -> list[WorkspaceBatch]:
        with connect(self._database_path) as connection:
            rows = connection.execute(
                """
                SELECT * FROM acquisition_workspace_batches
                ORDER BY created_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_batch_from_row(row) for row in rows]

    def get_batch(self, workspace_batch_id: str) -> tuple[WorkspaceBatch, list[AcquisitionCandidate]]:
        with connect(self._database_path) as connection:
            batch_row = connection.execute(
                "SELECT * FROM acquisition_workspace_batches WHERE workspace_batch_id = ?",
                (workspace_batch_id,),
            ).fetchone()
            if batch_row is None:
                raise KeyError(workspace_batch_id)
            candidate_rows = connection.execute(
                "SELECT candidate_json FROM acquisition_candidates WHERE workspace_batch_id = ? ORDER BY created_at ASC",
                (workspace_batch_id,),
            ).fetchall()
        candidates = [_candidate_from_json(row["candidate_json"]) for row in candidate_rows]
        return _batch_from_row(batch_row), candidates

    def save_candidate(self, candidate: AcquisitionCandidate) -> None:
        _assert_valid_candidate(candidate)
        now = datetime.now(tz=UTC).isoformat()
        with connect(self._database_path) as connection:
            connection.execute(
                """
                INSERT INTO acquisition_candidates (candidate_id, workspace_batch_id, candidate_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    candidate.candidate_id,
                    candidate.workspace_batch_id,
                    json.dumps(_candidate_to_json(candidate), ensure_ascii=False),
                    now,
                    now,
                ),
            )
            connection.commit()

    def update_candidate(self, candidate: AcquisitionCandidate) -> None:
        _assert_valid_candidate(candidate)
        now = datetime.now(tz=UTC).isoformat()
        with connect(self._database_path) as connection:
            connection.execute(
                """
                UPDATE acquisition_candidates SET candidate_json=?, updated_at=? WHERE candidate_id=?
                """,
                (json.dumps(_candidate_to_json(candidate), ensure_ascii=False), now, candidate.candidate_id),
            )
            connection.commit()

    def get_candidate(self, workspace_batch_id: str, candidate_id: str) -> AcquisitionCandidate:
        with connect(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT candidate_json FROM acquisition_candidates
                WHERE workspace_batch_id=? AND candidate_id=?
                """,
                (workspace_batch_id, candidate_id),
            ).fetchone()
        if row is None:
            raise KeyError(candidate_id)
        return _candidate_from_json(row["candidate_json"])

    def delete_candidate(self, workspace_batch_id: str, candidate_id: str) -> None:
        with connect(self._database_path) as connection:
            connection.execute(
                "DELETE FROM acquisition_candidates WHERE workspace_batch_id=? AND candidate_id=?",
                (workspace_batch_id, candidate_id),
            )
            connection.commit()

    def save_event(self, event: ImportEvent) -> None:
        with connect(self._database_path) as connection:
            connection.execute(
                """
                INSERT INTO acquisition_import_events (
                    event_id, workspace_batch_id, candidate_id, event_type, parser_strategy,
                    source_filename, source_file_hash, diagnostics_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.workspace_batch_id,
                    event.candidate_id,
                    event.event_type,
                    event.parser_strategy,
                    event.source_filename,
                    event.source_file_hash,
                    json.dumps(event.diagnostics, ensure_ascii=False),
                    event.created_at,
                ),
            )
            connection.commit()


def _batch_from_row(row) -> WorkspaceBatch:
    return WorkspaceBatch(
        workspace_batch_id=row["workspace_batch_id"],
        name=row["name"],
        source_type=row["source_type"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        total_rows=int(row["total_rows"]),
        accepted_count=int(row["accepted_count"]),
        warning_count=int(row["warning_count"]),
        rejected_count=int(row["rejected_count"]),
        duplicate_count=int(row["duplicate_count"]),
        selected_count=int(row["selected_count"]),
        status=row["status"],
    )


def _candidate_to_json(candidate: AcquisitionCandidate) -> dict:
    payload = asdict(candidate)
    for key, value in list(payload.items()):
        if isinstance(value, Decimal):
            payload[key] = str(value)
    return payload


def _candidate_from_json(raw: str) -> AcquisitionCandidate:
    data = json.loads(raw)
    for key in ("purchase_price", "purchase_price_jpy", "last_gross_profit", "last_net_profit"):
        if data.get(key) is not None:
            data[key] = Decimal(str(data[key]))
    data["detected_model_tokens"] = tuple(data.get("detected_model_tokens", []))
    data["validation_errors"] = tuple(data.get("validation_errors", []))
    data["validation_warnings"] = tuple(data.get("validation_warnings", []))
    data["yahoo_query_preview"] = tuple(data.get("yahoo_query_preview", []))
    truth = data.get("data_truth_summary") or {}
    metadata = data.get("discovery_metadata") or {}
    data["data_truth_summary"] = DataTruthSummary(
        reasons=tuple(truth.get("reasons", ())),
        **{key: value for key, value in truth.items() if key != "reasons"},
    )
    data["discovery_metadata"] = DiscoveryMetadata(
        query_used=tuple(metadata.get("query_used", ())),
        profit_analysis_version=str(metadata.get("profit_analysis_version") or ""),
        **{
            key: value
            for key, value in metadata.items()
            if key not in {"query_used", "profit_analysis_version"}
        },
    )
    candidate = AcquisitionCandidate(**data)
    _assert_valid_candidate(candidate)
    return candidate


def _assert_valid_candidate(candidate: AcquisitionCandidate) -> None:
    errors = validate_candidate_transparency(candidate)
    if errors:
        raise ValueError(f"Invalid acquisition candidate transparency metadata: {'; '.join(errors)}")
