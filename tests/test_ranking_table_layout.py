"""Focused ranking-table layout assertions (display-only column set)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app

FIXTURES = Path(__file__).resolve().parent / "fixtures"
BATCH_FIXTURES = FIXTURES / "batch_profit"


def test_workspace_ranking_table_desktop_layout_markers(tmp_path: Path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "layout.db"))
    with BATCH_FIXTURES.joinpath("candidates_valid.csv").open("rb") as handle:
        redirect = client.post(
            "/acquisition-workspace/import/csv",
            files={"csv_file": ("candidates_valid.csv", handle, "text/csv")},
            follow_redirects=False,
        )
    page = client.get(redirect.headers["location"])
    assert page.status_code == 200
    assert "page-acquisition-workspace" in page.text
    assert "ranking-table-wrap" in page.text
    assert "sticky-col-title" in page.text
    assert "data-ops-ranking-table" in page.text
    for header in (
        "商品名",
        "ブランド",
        "仕入価格",
        "販売予想価格",
        "純利益",
        "利益率",
        "販売価格信頼度",
        "総合リスク",
        "商品を見る",
    ):
        assert header in page.text
    ranking_header = page.text.split("data-ops-ranking-table", 1)[1].split("</thead>", 1)[0]
    for moved in ("順位", "ステータス", "ROI", "分析状態", "販売データ日付", "新品価格", "AI分析"):
        assert moved not in ranking_header
    assert "sticky-col-rank" not in ranking_header
    assert "販売データ日付" in page.text
    assert "新品価格詳細" in page.text
    assert "分析状態" in page.text


def test_workspace_ranking_css_dense_markers() -> None:
    css = (Path(__file__).resolve().parents[1] / "static" / "style.css").read_text(encoding="utf-8")
    assert "table-layout: fixed" in css
    assert ".ranking-table .col-brand" in css
    assert ".ranking-table .col-margin" in css
    assert ".ranking-table .col-confidence" in css
    assert ".ranking-table .btn-view" in css
    assert "max(100%, 1180px)" not in css
