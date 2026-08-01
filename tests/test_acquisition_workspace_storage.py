"""Tests for acquisition workspace SQLite storage."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.storage.acquisition_workspace_repository import AcquisitionWorkspaceRepository
from marketplace.acquisition_workspace.models import WorkspaceBatch
from tests.acquisition_test_helpers import make_candidate


def test_save_read_update_delete_candidate(tmp_path) -> None:
    repo = AcquisitionWorkspaceRepository(database_path=tmp_path / "ws.db")
    now = datetime.now(tz=UTC).isoformat()
    batch = WorkspaceBatch(
        workspace_batch_id="ws-001",
        name="Test",
        source_type="CSV",
        created_at=now,
        updated_at=now,
        total_rows=1,
        accepted_count=1,
        warning_count=0,
        rejected_count=0,
        duplicate_count=0,
        selected_count=0,
        status="COMPLETED",
    )
    repo.save_batch(batch)
    candidate = make_candidate(workspace_batch_id="ws-001")
    repo.save_candidate(candidate)
    loaded_batch, candidates = repo.get_batch("ws-001")
    assert loaded_batch.workspace_batch_id == "ws-001"
    assert len(candidates) == 1
    assert candidates[0].title == candidate.title

    updated = make_candidate(
        workspace_batch_id="ws-001",
        title="Updated Title",
    )
    updated.candidate_id = candidate.candidate_id
    repo.update_candidate(updated)
    reloaded = repo.get_candidate("ws-001", candidate.candidate_id)
    assert reloaded.title == "Updated Title"

    repo.delete_candidate("ws-001", candidate.candidate_id)
    _, after_delete = repo.get_batch("ws-001")
    assert after_delete == []


def test_multiple_batches_and_events(tmp_path) -> None:
    repo = AcquisitionWorkspaceRepository(database_path=tmp_path / "ws.db")
    now = datetime.now(tz=UTC).isoformat()
    for index in range(2):
        batch = WorkspaceBatch(
            workspace_batch_id=f"ws-{index}",
            name=f"Batch {index}",
            source_type="CSV",
            created_at=now,
            updated_at=now,
            total_rows=0,
            accepted_count=0,
            warning_count=0,
            rejected_count=0,
            duplicate_count=0,
            selected_count=0,
            status="OPEN",
        )
        repo.save_batch(batch)
    batches = repo.list_batches(limit=10)
    assert len(batches) == 2

    from marketplace.acquisition_workspace.models import ImportEvent

    repo.save_event(
        ImportEvent(
            event_id=f"evt-{uuid4().hex[:8]}",
            workspace_batch_id="ws-0",
            candidate_id="",
            event_type="IMPORT_WARNINGS",
            parser_strategy="csv",
            source_filename="test.csv",
            source_file_hash="abc",
            diagnostics={"errors": ["line 2: skip"]},
            created_at=now,
        )
    )


def test_existing_db_compatibility(tmp_path) -> None:
    db_path = tmp_path / "brand_profit.db"
    repo = AcquisitionWorkspaceRepository(database_path=db_path)
    now = datetime.now(tz=UTC).isoformat()
    repo.save_batch(
        WorkspaceBatch(
            workspace_batch_id="ws-compat",
            name="Compat",
            source_type="MANUAL",
            created_at=now,
            updated_at=now,
            total_rows=0,
            accepted_count=0,
            warning_count=0,
            rejected_count=0,
            duplicate_count=0,
            selected_count=0,
            status="OPEN",
        )
    )
    _, rows = repo.get_batch("ws-compat")
    assert rows == []


def test_candidate_transparency_round_trip(tmp_path) -> None:
    repo = AcquisitionWorkspaceRepository(database_path=tmp_path / "ws.db")
    now = datetime.now(tz=UTC).isoformat()
    repo.save_batch(
        WorkspaceBatch(
            workspace_batch_id="ws-truth",
            name="Truth",
            source_type="CSV",
            created_at=now,
            updated_at=now,
            total_rows=0,
            accepted_count=0,
            warning_count=0,
            rejected_count=0,
            duplicate_count=0,
            selected_count=0,
            status="OPEN",
        )
    )
    candidate = make_candidate(workspace_batch_id="ws-truth")
    repo.save_candidate(candidate)
    loaded = repo.get_candidate("ws-truth", candidate.candidate_id)
    assert loaded.data_truth_summary.confidence_level == "HIGH"
    assert loaded.discovery_metadata.runtime_mode == "IMPORT"
    assert loaded.discovery_metadata.query_count == 1


def test_invalid_transparency_metadata_raises(tmp_path) -> None:
    repo = AcquisitionWorkspaceRepository(database_path=tmp_path / "ws.db")
    now = datetime.now(tz=UTC).isoformat()
    repo.save_batch(
        WorkspaceBatch(
            workspace_batch_id="ws-invalid",
            name="Invalid",
            source_type="CSV",
            created_at=now,
            updated_at=now,
            total_rows=0,
            accepted_count=0,
            warning_count=0,
            rejected_count=0,
            duplicate_count=0,
            selected_count=0,
            status="OPEN",
        )
    )
    candidate = make_candidate(workspace_batch_id="ws-invalid")
    candidate.data_truth_summary.confidence_level = ""
    candidate.discovery_metadata.runtime_mode = ""
    candidate.discovery_metadata.query_count = 0
    candidate.discovery_metadata.candidate_count = 0
    candidate.discovery_metadata.comparable_count = 1
    with pytest.raises(ValueError, match="confidence_level is required"):
        repo.save_candidate(candidate)
