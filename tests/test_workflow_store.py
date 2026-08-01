"""Unit tests for candidate workflow store (status + notes)."""

from __future__ import annotations

from pathlib import Path

import pytest

from marketplace.acquisition_workspace.workflow import (
    CandidateWorkflowStore,
    DEFAULT_STATUS,
    filter_choices,
    normalize_status,
    selectable_statuses,
    status_label,
)


def test_default_status_and_labels() -> None:
    assert DEFAULT_STATUS == "unchecked"
    assert status_label("unchecked") == "未確認"
    assert status_label("reviewing") == "検討中"
    assert status_label("hold") == "保留"
    assert status_label("purchase_planned") == "購入予定"
    assert [item.code for item in selectable_statuses()] == [
        "unchecked",
        "reviewing",
        "hold",
        "purchase_planned",
    ]
    assert filter_choices()[0] == {"code": "all", "label": "すべて"}


def test_workflow_store_persists_status_and_notes(tmp_path: Path) -> None:
    path = tmp_path / "workflow.json"
    store = CandidateWorkflowStore(storage_path=path)
    updated = store.set_status("c1", "reviewing")
    assert updated.status == "reviewing"
    assert updated.label() == "検討中"

    noted = store.set_notes("c1", "箱なし\n角スレあり")
    assert noted.notes == "箱なし\n角スレあり"
    assert noted.status == "reviewing"

    reloaded = CandidateWorkflowStore(storage_path=path)
    loaded = reloaded.get("c1")
    assert loaded.status == "reviewing"
    assert loaded.notes == "箱なし\n角スレあり"


def test_normalize_status_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        normalize_status("purchased")
