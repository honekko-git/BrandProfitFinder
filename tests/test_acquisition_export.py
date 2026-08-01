"""Tests for acquisition workspace export."""

from __future__ import annotations

import json
from pathlib import Path

from marketplace.acquisition_workspace.exporters import export_candidates_csv, export_candidates_json
from tests.acquisition_test_helpers import make_candidate


def test_csv_export_selected_fields(tmp_path: Path) -> None:
    candidate = make_candidate(selected=True, data_status="IMPORT")
    path = tmp_path / "all.csv"
    export_candidates_csv(path, [candidate])
    text = path.read_text(encoding="utf-8")
    assert "Chanel Classic Wallet" in text
    assert "IMPORT" in text
    assert "candidate_id" in text.splitlines()[0]


def test_json_export_no_raw_html(tmp_path: Path) -> None:
    candidate = make_candidate()
    path = tmp_path / "data.json"
    export_candidates_json(path, [candidate])
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert len(payload) == 1
    serialized = json.dumps(payload)
    assert "<html" not in serialized.lower()
    assert "cookie" not in serialized.lower()
    assert payload[0]["title"] == candidate.title


def test_export_creates_output_directory(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "out" / "selected.csv"
    export_candidates_csv(path, [make_candidate(selected=True)])
    assert path.exists()
