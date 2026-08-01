"""Browser tests for candidate workflow management."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app

FIXTURES = Path(__file__).resolve().parent / "fixtures"
BATCH_FIXTURES = FIXTURES / "batch_profit"


def test_ranking_shows_status_and_filters(tmp_path: Path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "workflow-rank.db"))
    page = client.get("/acquisition-workspace?demo=1")
    assert page.status_code == 200
    assert "未確認" in page.text
    assert "検討中" in page.text
    assert "保留" in page.text
    assert "購入予定" in page.text
    assert "すべて" in page.text
    assert 'data-component="StatusBadge"' in page.text
    assert 'data-component="StatusSelector"' in page.text
    assert 'data-workflow-filter="unchecked"' in page.text
    assert "data-workflow-status=" in page.text


def test_status_update_and_detail_sync(tmp_path: Path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "workflow-status.db"))
    candidate_id = "demo-01-chanel-wallet"

    ranking = client.get("/acquisition-workspace?demo=1")
    assert ranking.status_code == 200
    assert "未確認" in ranking.text

    updated = client.post(
        f"/acquisition-workspace/workflow/{candidate_id}",
        json={"status": "purchase_planned"},
    )
    assert updated.status_code == 200
    payload = updated.json()
    assert payload["ok"] is True
    assert payload["workflow"]["status"] == "purchase_planned"
    assert payload["workflow"]["label"] == "購入予定"

    ranking_after = client.get("/acquisition-workspace?demo=1")
    assert ranking_after.status_code == 200
    assert "購入予定" in ranking_after.text
    assert 'data-workflow-status="purchase_planned"' in ranking_after.text

    detail = client.get(
        f"/acquisition-workspace/candidate/{candidate_id}?batch_id=demo-workspace&demo=1"
    )
    assert detail.status_code == 200
    assert "購入予定" in detail.text
    assert 'data-component="CandidateActionBar"' in detail.text
    assert 'selected' in detail.text
    assert "purchase_planned" in detail.text


def test_notes_save_and_detail_display(tmp_path: Path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "workflow-notes.db"))
    candidate_id = "demo-01-chanel-wallet"
    note = "箱なし\n角スレあり\n値下げ待ち"

    saved = client.post(
        f"/acquisition-workspace/workflow/{candidate_id}",
        json={"notes": note},
    )
    assert saved.status_code == 200
    assert saved.json()["workflow"]["notes"] == note

    detail = client.get(
        f"/acquisition-workspace/candidate/{candidate_id}?batch_id=demo-workspace&demo=1"
    )
    assert detail.status_code == 200
    assert 'data-component="NotePanel"' in detail.text
    assert "箱なし" in detail.text
    assert "角スレあり" in detail.text
    assert "メモを保存" in detail.text


def test_real_candidate_workflow_filter_param(tmp_path: Path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "workflow-real.db"))
    with BATCH_FIXTURES.joinpath("candidates_valid.csv").open("rb") as handle:
        redirect = client.post(
            "/acquisition-workspace/import/csv",
            files={"csv_file": ("candidates_valid.csv", handle, "text/csv")},
            follow_redirects=False,
        )
    batch_url = redirect.headers["location"]
    batch_id = batch_url.split("batch_id=")[-1]

    ranking = client.get(batch_url)
    assert ranking.status_code == 200
    assert "デモ表示中" not in ranking.text
    assert 'data-workflow-filter="all"' in ranking.text

    marker = "/acquisition-workspace/candidate/"
    start = ranking.text.index(marker)
    end = ranking.text.index('"', start)
    detail_path = ranking.text[start:end].replace("&amp;", "&")
    candidate_id = detail_path.split("/candidate/")[1].split("?")[0]

    client.post(
        f"/acquisition-workspace/workflow/{candidate_id}",
        json={"status": "hold", "notes": "店舗A"},
    )
    filtered = client.get(f"/acquisition-workspace?batch_id={batch_id}&status=hold")
    assert filtered.status_code == 200
    assert 'data-workflow-filter="hold"' in filtered.text
    assert "is-active" in filtered.text

    detail = client.get(detail_path)
    assert detail.status_code == 200
    assert "保留" in detail.text
    assert "店舗A" in detail.text
