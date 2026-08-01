"""Browser tests for acquisition sourcing detail workspace."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from marketplace.acquisition_workspace.detail_display import split_analysis_sections

FIXTURES = Path(__file__).resolve().parent / "fixtures"
BATCH_FIXTURES = FIXTURES / "batch_profit"


def test_split_analysis_sections_reorganizes_existing_text_only() -> None:
    positives, cautions, summary = split_analysis_sections(
        "利益率が高く、販売実績も安定しています。購入前に状態と付属品をご確認ください。"
    )
    assert any("利益率が高く" in item for item in positives)
    assert any("確認" in item for item in cautions)
    assert summary == [] or all(isinstance(item, str) for item in summary)

    empty_p, empty_c, empty_s = split_analysis_sections("")
    assert empty_p == []
    assert empty_c == []
    assert empty_s == []


def test_openapi_includes_candidate_detail_route(tmp_path: Path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "openapi-detail.db"))
    spec = client.get("/openapi.json")
    assert spec.status_code == 200
    paths = spec.json()["paths"]
    assert "/acquisition-workspace/candidate/{candidate_id}" in paths
    methods = paths["/acquisition-workspace/candidate/{candidate_id}"]
    assert "get" in methods


def test_demo_ranking_links_to_detail_page(tmp_path: Path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "demo.db"))
    ranking = client.get("/acquisition-workspace?demo=1")
    assert ranking.status_code == 200
    assert "/acquisition-workspace/candidate/demo-01-chanel-wallet" in ranking.text
    assert "data-save-ranking-scroll" in ranking.text
    assert "title-brand" in ranking.text
    assert "analysis-one-line" in ranking.text
    assert "analysis-badge" in ranking.text

    detail = client.get(
        "/acquisition-workspace/candidate/demo-01-chanel-wallet?batch_id=demo-workspace&demo=1"
    )
    assert detail.status_code == 200
    assert detail.text.count("← ランキングへ戻る") >= 2
    assert 'data-restore-ranking-scroll="1"' in detail.text
    assert "デモ表示中" in detail.text
    assert "マトラッセ キャビアスキン 長財布" in detail.text

    # Decision hierarchy first: score / prices / profit / ROI
    assert "sourcing-decision-summary" in detail.text
    assert "総合評価" in detail.text
    assert "仕入価格" in detail.text
    assert "販売予想価格" in detail.text
    assert "純利益" in detail.text
    assert "ROI" in detail.text
    assert "¥" in detail.text
    assert 'data-component="PriceCard"' not in detail.text

    # Market information (existing sales metrics)
    assert 'data-section="MarketInformation"' in detail.text
    assert "マーケット情報" in detail.text
    assert 'data-component="SalesInfo"' in detail.text
    assert "Sold件数" in detail.text or "販売件数" in detail.text

    # Collapsible profit breakdown
    assert 'data-component="ProfitBreakdown"' in detail.text
    assert "<details" in detail.text
    assert "利益内訳" in detail.text
    assert "Yahooオークション販売手数料" in detail.text or "国内販売手数料" in detail.text
    assert "eBay手数料" not in detail.text
    assert "決済手数料" in detail.text
    assert "国内送料" in detail.text
    assert "国際送料" in detail.text
    assert "関税" in detail.text or "輸入消費税" in detail.text
    assert "その他固定費" in detail.text or "その他費用" in detail.text
    assert "最終利益" in detail.text or "純利益" in detail.text

    # AI above warnings
    assert detail.text.index('data-component="AIAnalysisPanel"') < detail.text.index(
        'data-component="WarningList"'
    )
    assert 'data-component="AIAnalysisPanel"' in detail.text
    assert "【良い点】" in detail.text
    assert "【注意点】" in detail.text
    assert "【総合コメント】" in detail.text
    assert "利益率が高く、販売実績も安定しています" in detail.text

    # Warnings / actions
    assert 'data-component="WarningList"' in detail.text
    assert "注意事項" in detail.text
    assert "価格推定" in detail.text or "状態確認" in detail.text
    assert 'data-component="ActionPanel"' in detail.text
    assert "商品ページを開く" in detail.text
    assert 'target="_blank"' in detail.text
    assert "https://example.com/demo/chanel-wallet" in detail.text

    # Management at bottom (workflow + notes)
    assert 'data-section="management"' in detail.text
    assert ">管理<" in detail.text or "管理" in detail.text
    assert 'data-component="CandidateActionBar"' in detail.text
    assert 'data-component="NotePanel"' in detail.text
    assert detail.text.index('data-component="ActionPanel"') < detail.text.index(
        'data-section="management"'
    )
    assert detail.text.index('data-section="management"') < detail.text.index(
        'sourcing-detail-nav-bottom'
    )

    assert 'href="/acquisition-workspace"' in detail.text
    assert 'data-extension-slot="notes"' in detail.text
    assert 'data-extension-slot="watchlist"' in detail.text


def test_real_candidate_detail_and_back_navigation(tmp_path: Path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "real.db"))
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
    assert "/acquisition-workspace/candidate/" in ranking.text
    assert f"batch_id={batch_id}" in ranking.text

    marker = "/acquisition-workspace/candidate/"
    start = ranking.text.index(marker)
    end = ranking.text.index('"', start)
    detail_path = ranking.text[start:end].replace("&amp;", "&")
    detail = client.get(detail_path)
    assert detail.status_code == 200
    assert detail.text.count("← ランキングへ戻る") >= 2
    assert f"batch_id={batch_id}" in detail.text
    assert "sourcing-decision-summary" in detail.text
    assert "仕入価格" in detail.text
    assert "販売予想価格" in detail.text
    assert "マーケット情報" in detail.text
    assert 'data-component="ProfitBreakdown"' in detail.text
    assert "利益内訳" in detail.text
    assert 'data-component="AIAnalysisPanel"' in detail.text
    assert "【良い点】" in detail.text
    assert 'data-section="management"' in detail.text
    assert "商品ページを開く" in detail.text or "商品ページURLが未設定または無効です" in detail.text


def test_demo_detail_listing_button_opens_example_url(tmp_path: Path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "demo-listing.db"))
    detail = client.get(
        "/acquisition-workspace/candidate/demo-01-chanel-wallet?batch_id=demo-workspace&demo=1"
    )
    assert detail.status_code == 200
    assert 'href="https://example.com/demo/chanel-wallet"' in detail.text
    assert "商品ページを開く" in detail.text
