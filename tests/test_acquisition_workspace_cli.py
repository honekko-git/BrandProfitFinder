"""Tests for acquisition workspace CLI."""

from __future__ import annotations

import json
import os
from io import StringIO
from pathlib import Path

from profit_discovery.cli.acquisition_workspace_command import run_acquisition_cli
from profit_discovery.discovery_validation.batch_profit.pipeline import run_batch_profit as _real_run_batch_profit

FIXTURES = Path(__file__).resolve().parent / "fixtures"
BATCH_FIXTURES = FIXTURES / "batch_profit"
HTML_FIXTURES = FIXTURES / "browser_acquisition"


def test_cli_csv_import_and_list(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "cli.db"
    monkeypatch.setenv("BRAND_PROFIT_DB_PATH", str(db_path))
    out = StringIO()
    code = run_acquisition_cli(
        ["acquisition-import", "--csv", str(BATCH_FIXTURES / "candidates_valid.csv")],
        output=out,
    )
    assert code == 0
    assert "Imported workspace batch" in out.getvalue()

    from app.storage.acquisition_workspace_repository import AcquisitionWorkspaceRepository

    batches = AcquisitionWorkspaceRepository(database_path=db_path).list_batches()
    assert batches

    list_out = StringIO()
    run_acquisition_cli(
        ["acquisition-list", "--workspace-batch-id", batches[0].workspace_batch_id, "--eligible-only"],
        output=list_out,
    )
    assert "Chanel" in list_out.getvalue()


def test_cli_html_import(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "cli-html.db"
    monkeypatch.setenv("BRAND_PROFIT_DB_PATH", str(db_path))
    out = StringIO()
    code = run_acquisition_cli(
        ["acquisition-import", "--html", str(HTML_FIXTURES / "fashionphile_search_results.html")],
        output=out,
    )
    assert code == 0
    assert "Imported HTML batch" in out.getvalue()


def test_cli_export_selected(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "cli-export.db"
    monkeypatch.setenv("BRAND_PROFIT_DB_PATH", str(db_path))
    run_acquisition_cli(["acquisition-import", "--csv", str(BATCH_FIXTURES / "candidates_valid.csv")])
    from app.storage.acquisition_workspace_repository import AcquisitionWorkspaceRepository
    from marketplace.acquisition_workspace.workspace_service import AcquisitionWorkspaceService

    repo = AcquisitionWorkspaceRepository(database_path=db_path)
    service = AcquisitionWorkspaceService(repo)
    batch = repo.list_batches()[0]
    service.select_all_eligible(batch.workspace_batch_id)
    out_path = tmp_path / "selected.csv"
    json_path = tmp_path / "selected.json"
    out = StringIO()
    code = run_acquisition_cli(
        [
            "acquisition-export",
            "--workspace-batch-id",
            batch.workspace_batch_id,
            "--selected-only",
            "--output-csv",
            str(out_path),
            "--output-json",
            str(json_path),
        ],
        output=out,
    )
    assert code == 0
    assert out_path.exists()
    assert json_path.exists()
    assert "Chanel" in out_path.read_text(encoding="utf-8")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload[0]["data_truth_summary"]["confidence_level"]
    assert payload[0]["discovery_metadata"]["runtime_mode"] == "IMPORT"


def test_cli_run_profit_with_fixture_html(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "cli-profit.db"
    monkeypatch.setenv("BRAND_PROFIT_DB_PATH", str(db_path))
    run_acquisition_cli(["acquisition-import", "--csv", str(BATCH_FIXTURES / "candidates_valid.csv")])
    from app.storage.acquisition_workspace_repository import AcquisitionWorkspaceRepository

    batch_id = AcquisitionWorkspaceRepository(database_path=db_path).list_batches()[0].workspace_batch_id
    yahoo_html = HTML_FIXTURES.joinpath("yahoo_live_ja.html").read_text(encoding="utf-8")

    def _inject_html(candidates, **kwargs):
        kwargs["html_by_query"] = {query: yahoo_html for query in [
            "シャネル キャビアスキン 財布 黒",
            "シャネル クラシック 財布",
            "CHANEL wallet caviar black",
        ]}
        return _real_run_batch_profit(candidates, **kwargs)

    monkeypatch.setattr(
        "profit_discovery.discovery_validation.batch_profit.pipeline.run_batch_profit",
        _inject_html,
    )
    out = StringIO()
    code = run_acquisition_cli(
        [
            "acquisition-run-profit",
            "--workspace-batch-id",
            batch_id,
            "--selected-only",
            "--limit",
            "2",
            "--cost-profile",
            "standard",
        ],
        output=out,
    )
    assert code == 0
    assert "利益バッチ" in out.getvalue()


def test_cli_list_supports_summary_and_confidence_sort(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "cli-summary.db"
    monkeypatch.setenv("BRAND_PROFIT_DB_PATH", str(db_path))
    run_acquisition_cli(["acquisition-import", "--csv", str(BATCH_FIXTURES / "candidates_valid.csv")])
    from app.storage.acquisition_workspace_repository import AcquisitionWorkspaceRepository
    from marketplace.acquisition_workspace.workspace_service import AcquisitionWorkspaceService

    repo = AcquisitionWorkspaceRepository(database_path=db_path)
    service = AcquisitionWorkspaceService(repo)
    batch = repo.list_batches()[0]
    service.select_all_eligible(batch.workspace_batch_id)

    yahoo_html = HTML_FIXTURES.joinpath("yahoo_live_ja.html").read_text(encoding="utf-8")

    def _inject_html(candidates, **kwargs):
        kwargs["html_by_query"] = {query: yahoo_html for query in [
            "シャネル キャビアスキン 財布 黒",
            "シャネル クラシック 財布",
            "CHANEL wallet caviar black",
        ]}
        return _real_run_batch_profit(candidates, **kwargs)

    monkeypatch.setattr(
        "profit_discovery.discovery_validation.batch_profit.pipeline.run_batch_profit",
        _inject_html,
    )
    service.run_batch_profit(batch.workspace_batch_id, use_cache=False)
    out = StringIO()
    code = run_acquisition_cli(
        [
            "acquisition-list",
            "--workspace-batch-id",
            batch.workspace_batch_id,
            "--summary",
            "--sort",
            "confidence",
            "--limit",
            "2",
        ],
        output=out,
    )
    rendered = out.getvalue()
    assert code == 0
    assert "ワークスペース概要" in rendered
    assert "平均信頼度:" in rendered
    assert "データ取得情報" in rendered
    assert "信頼度:" in rendered
