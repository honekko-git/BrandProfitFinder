"""Tests for batch profit browser UI."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.storage.batch_profit_repository import BatchProfitRepository
from app.store import BatchProfitResultStore

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "batch_profit"


def test_profit_batch_page_renders() -> None:
    client = TestClient(create_app())
    response = client.get("/profit-batch")
    assert response.status_code == 200
    assert "一括利益計算" in response.text


def test_csv_upload_runs_batch_with_fixture_html(tmp_path: Path, monkeypatch) -> None:
    yahoo_html = (
        Path(__file__).resolve().parent / "fixtures" / "browser_acquisition" / "yahoo_live_ja.html"
    ).read_text(encoding="utf-8")

    def _fake_run_batch_profit(candidates, **kwargs):
        kwargs["html_by_query"] = {"シャネル クラシック 財布": yahoo_html}
        from profit_discovery.discovery_validation.batch_profit.pipeline import run_batch_profit as real_run

        return real_run(candidates, **kwargs)

    monkeypatch.setattr("app.batch_profit_pipeline.run_batch_profit", _fake_run_batch_profit)

    store = BatchProfitResultStore()
    client = TestClient(
        create_app(
            validation_store=None,
            database_path=tmp_path / "web.db",
        )
    )
    client.app.state.batch_profit_store = store
    with FIXTURES.joinpath("candidates_valid.csv").open("rb") as handle:
        response = client.post(
            "/profit-batch/run",
            data={"cost_profile": "standard", "candidate_limit": "2", "use_cache": "on"},
            files={"csv_file": ("candidates_valid.csv", handle, "text/csv")},
        )
    assert response.status_code == 200
    assert "バッチID" in response.text or "順位" in response.text


def test_batch_history_listing(tmp_path: Path) -> None:
    repo = BatchProfitRepository(database_path=tmp_path / "history.db")
    client = TestClient(create_app())
    response = client.get("/profit-batch")
    assert response.status_code == 200
    assert "バッチ履歴" in response.text
