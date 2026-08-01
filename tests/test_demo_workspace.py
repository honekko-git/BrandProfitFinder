"""Tests for in-memory Acquisition Workspace demo dashboard."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from marketplace.acquisition_workspace.demo_workspace import DemoWorkspaceProvider

FIXTURES = Path(__file__).resolve().parent / "fixtures"
BATCH_FIXTURES = FIXTURES / "batch_profit"


def test_demo_workspace_provider_builds_in_memory_dataset() -> None:
    demo = DemoWorkspaceProvider.build()
    assert 8 <= len(demo.rows) <= 10
    assert demo.batch.workspace_batch_id == "demo-workspace"
    assert demo.workspace_summary["candidates"] == len(demo.rows)
    assert demo.workspace_summary["profit_checked"] == len(demo.rows)
    assert demo.workspace_summary["pending"] == 2
    assert demo.workspace_summary["last_updated"] == "本日 10:30"
    assert all(row.purchase_url.startswith("https://example.com/demo/") for row in demo.rows)
    assert all(row.candidate_id in demo.ranking_by_id for row in demo.rows)


def test_zero_candidates_shows_empty_workspace_not_demo(tmp_path: Path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "demo.db"))
    page = client.get("/acquisition-workspace")
    assert page.status_code == 200
    assert "デモ表示中" not in page.text
    assert "No acquisition candidates have been imported." in page.text
    assert "CHANEL マトラッセ キャビアスキン 長財布" not in page.text
    assert "example.com/demo/" not in page.text
    assert "No analyzed opportunities." in page.text


def test_explicit_demo_query_shows_demo_workspace(tmp_path: Path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "demo-explicit.db"))
    page = client.get("/acquisition-workspace?demo=1")
    assert page.status_code == 200
    assert "デモ表示中" in page.text
    assert "開発用の明示的デモモード" in page.text
    assert "CHANEL マトラッセ キャビアスキン 長財布" in page.text or "マトラッセ キャビアスキン 長財布" in page.text
    assert "¥32,800" in page.text
    assert "仕入" in page.text
    assert "販売予想" in page.text
    assert "¥104,250" in page.text
    assert "¥148,000" in page.text
    assert "title-brand" in page.text
    assert "analysis-badge" in page.text
    assert "10 / 10件" in page.text or " / " in page.text
    assert "本日 10:30" in page.text
    assert "example.com/demo/" in page.text or "/acquisition-workspace/candidate/demo-" in page.text
    assert "ランキングはまだ作成されていません" not in page.text
    assert 'action="/acquisition-workspace/demo-workspace/run-profit"' not in page.text


def test_real_candidates_hide_demo_workspace(tmp_path: Path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "real.db"))
    with BATCH_FIXTURES.joinpath("candidates_valid.csv").open("rb") as handle:
        redirect = client.post(
            "/acquisition-workspace/import/csv",
            files={"csv_file": ("candidates_valid.csv", handle, "text/csv")},
            follow_redirects=False,
        )
    page = client.get(redirect.headers["location"])
    assert page.status_code == 200
    assert "デモ表示中" not in page.text
    assert "サンプルデータを表示しています" not in page.text
    assert "Chanel Classic Wallet" in page.text
    assert "CHANEL マトラッセ キャビアスキン 長財布" not in page.text
    assert "example.com/demo/" not in page.text


def test_past_history_opens_latest_real_batch_on_landing(tmp_path: Path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "history.db"))
    with BATCH_FIXTURES.joinpath("candidates_valid.csv").open("rb") as handle:
        client.post(
            "/acquisition-workspace/import/csv",
            files={"csv_file": ("candidates_valid.csv", handle, "text/csv")},
            follow_redirects=False,
        )
    landing = client.get("/acquisition-workspace")
    assert landing.status_code == 200
    assert "デモ表示中" not in landing.text
    assert "Chanel Classic Wallet" in landing.text
    assert "マトラッセ キャビアスキン 長財布" not in landing.text


def test_should_use_demo_requires_explicit_flag() -> None:
    history_with_rows = [type("Batch", (), {"total_rows": 5})()]
    assert DemoWorkspaceProvider.should_use_demo(current_rows=[], history=history_with_rows) is False
    assert DemoWorkspaceProvider.should_use_demo(current_rows=[], history=[], explicit_demo=False) is False
    assert DemoWorkspaceProvider.should_use_demo(current_rows=[], history=[], explicit_demo=True) is True
    assert DemoWorkspaceProvider.should_use_demo(current_rows=["real"], history=[], explicit_demo=True) is True
    assert DemoWorkspaceProvider.should_use_demo(current_rows=[], history=[], explicit_demo=1) is False  # type: ignore[arg-type]


def test_empty_workspace_sets_no_store_cache_header(tmp_path: Path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "cache.db"))
    page = client.get("/acquisition-workspace")
    assert page.status_code == 200
    assert "no-store" in page.headers.get("cache-control", "").lower()
    assert "デモ表示中" not in page.text
    assert "demo-01-chanel-wallet" not in page.text


def test_demo_candidate_detail_requires_explicit_query(tmp_path: Path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "demo-detail.db"))
    blocked = client.get(
        "/acquisition-workspace/candidate/demo-01-chanel-wallet?batch_id=demo-workspace"
    )
    assert blocked.status_code == 404
    allowed = client.get(
        "/acquisition-workspace/candidate/demo-01-chanel-wallet?batch_id=demo-workspace&demo=1"
    )
    assert allowed.status_code == 200
    assert "マトラッセ" in allowed.text


def test_smoke_fixture_batches_do_not_auto_open(tmp_path: Path) -> None:
    """Operational landing must not surface smoke_candidates CSV leftovers."""
    from app.storage.acquisition_workspace_repository import AcquisitionWorkspaceRepository
    from marketplace.acquisition_workspace.workspace_service import AcquisitionWorkspaceService

    db = tmp_path / "smoke-ops.db"
    service = AcquisitionWorkspaceService(AcquisitionWorkspaceRepository(database_path=db))
    csv_path = Path(__file__).resolve().parent.parent / "data" / "uploads" / "smoke_candidates.csv"
    assert csv_path.exists()
    batch = service.import_csv(csv_path, name="smoke_candidates.csv")
    assert "smoke" in batch.name.lower()

    client = TestClient(create_app(database_path=db))
    page = client.get("/acquisition-workspace")
    assert page.status_code == 200
    assert "SMOKE TEST" not in page.text
    assert "No acquisition candidates have been imported." in page.text

    # Direct deep-link to the smoke batch is also blocked.
    linked = client.get(f"/acquisition-workspace?batch_id={batch.workspace_batch_id}")
    assert linked.status_code == 200
    assert "SMOKE TEST" not in linked.text
    assert "No acquisition candidates have been imported." in linked.text


def test_demo_detail_payload_is_complete() -> None:
    found = DemoWorkspaceProvider.find_candidate("demo-01-chanel-wallet")
    assert found is not None
    assert found["selling_estimate"] == Decimal("148000")
    assert found["detail"]["breakdown"]
    assert found["detail"]["sales_info"]
    assert "利益率が高く" in found["detail"]["analysis"]
