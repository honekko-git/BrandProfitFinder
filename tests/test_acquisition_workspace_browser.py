"""Tests for acquisition workspace browser UI."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from profit_discovery.discovery_validation.batch_profit.pipeline import run_batch_profit as _real_run_batch_profit

FIXTURES = Path(__file__).resolve().parent / "fixtures"
BATCH_FIXTURES = FIXTURES / "batch_profit"
HTML_FIXTURES = FIXTURES / "browser_acquisition"


def test_acquisition_workspace_page_route(tmp_path: Path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "web.db"))
    response = client.get("/acquisition-workspace")
    assert response.status_code == 200
    assert "仕入れ候補ワークスペース" in response.text
    assert "仕入れ候補の確認・利益計算・管理を行います" in response.text
    assert "商品を追加" in response.text
    assert "ランキング" in response.text
    assert "候補数" in response.text
    assert "利益計算済" in response.text
    assert "要確認" in response.text
    assert "最終更新" in response.text
    assert "CSV取込" in response.text
    assert "手動入力" in response.text
    assert "HTMLファイル取込" in response.text
    assert "商品URL追加" in response.text
    assert "保存済み候補をコピー" in response.text
    assert response.text.index("<h3>CSV取込</h3>") < response.text.index("<h3>商品URL追加</h3>")
    assert response.text.index("<h3>商品URL追加</h3>") < response.text.index("<h3>保存済み候補をコピー</h3>")
    assert response.text.index("<h3>保存済み候補をコピー</h3>") < response.text.index("<h3>HTMLファイル取込</h3>")
    assert "デモ表示中" not in response.text
    assert "No acquisition candidates have been imported." in response.text
    assert "No analyzed opportunities." in response.text
    assert "Fashionphile検索" in response.text
    assert "Rebag検索" in response.text
    assert "The RealReal検索" in response.text
    assert "Vestiaire Collective検索" in response.text
    assert "＋入力欄を追加" in response.text
    assert 'name="title_0"' in response.text
    assert 'name="title_2"' in response.text
    assert 'name="title_3"' not in response.text
    assert "詳細設定" in response.text
    assert "カスタムコスト設定" in response.text
    assert "取込履歴" in response.text
    assert response.text.index('id="summary"') < response.text.index('id="ranking"')
    assert response.text.index('id="ranking"') < response.text.index('id="intake"')
    assert response.text.index('id="intake"') < response.text.index('id="advanced"')


def test_csv_import_shows_batch_summary(tmp_path: Path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "web.db"))
    with BATCH_FIXTURES.joinpath("candidates_valid.csv").open("rb") as handle:
        response = client.post(
            "/acquisition-workspace/import/csv",
            files={"csv_file": ("candidates_valid.csv", handle, "text/csv")},
            follow_redirects=False,
        )
    assert response.status_code == 303
    batch_url = response.headers["location"]
    page = client.get(batch_url)
    assert page.status_code == 200
    assert "利益計算" in page.text
    assert "ランキング" in page.text
    assert "Chanel Classic Wallet" in page.text
    assert "候補数" in page.text
    assert "利益計算済" in page.text
    assert "要確認" in page.text
    assert "最終更新" in page.text
    assert "平均信頼度" in page.text
    assert "商品を見る" in page.text or "商品ページURLが未設定または無効です" in page.text
    assert "順位" in page.text
    assert "商品名" in page.text
    assert "仕入価格" in page.text or "価格" in page.text
    assert "仕入" in page.text
    assert "販売予想" in page.text
    assert "総合評価" in page.text or "利益率" in page.text
    assert "AI分析" in page.text
    assert "analysis-one-line" in page.text or "analysis-badge" in page.text or "販売価格信頼度" in page.text
    assert " / " in page.text and "件" in page.text
    assert page.text.index("<h3>CSV取込</h3>") < page.text.index("<h3>商品URL追加</h3>")
    assert page.text.index("<h3>商品URL追加</h3>") < page.text.index("<h3>保存済み候補をコピー</h3>")
    assert page.text.index("<h3>保存済み候補をコピー</h3>") < page.text.index("<h3>HTMLファイル取込</h3>")
    assert page.text.index('id="summary"') < page.text.index('id="ranking"')
    assert page.text.index('id="ranking"') < page.text.index('id="intake"')
    assert "デモ表示中" not in page.text
    assert "example.com/demo/" not in page.text


def test_manual_import_and_data_status(tmp_path: Path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "web.db"))
    response = client.post(
        "/acquisition-workspace/import/manual",
        data={
            "title_0": "Chanel Classic Wallet Black Caviar",
            "price_0": "695",
            "currency_0": "USD",
            "url_0": "https://www.fashionphile.com/p/chanel-classic-wallet",
            "source_0": "Manual",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    page = client.get(response.headers["location"])
    assert "IMPORT" in page.text or "Chanel Classic Wallet" in page.text


def test_saved_html_import(tmp_path: Path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "web.db"))
    html = HTML_FIXTURES.joinpath("fashionphile_search_results.html").read_bytes()
    response = client.post(
        "/acquisition-workspace/import/html",
        files={"html_files": ("fashionphile_search_results.html", BytesIO(html), "text/html")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert "batch_id=" in location
    page = client.get(location)
    assert "PARSED_SAVED_HTML" in page.text or "Chanel Classic Wallet" in page.text or "Fashionphile" in page.text


def test_select_all_and_run_profit(tmp_path: Path, monkeypatch) -> None:
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

    client = TestClient(create_app(database_path=tmp_path / "web.db"))
    with BATCH_FIXTURES.joinpath("candidates_valid.csv").open("rb") as handle:
        redirect = client.post(
            "/acquisition-workspace/import/csv",
            files={"csv_file": ("candidates_valid.csv", handle, "text/csv")},
            follow_redirects=False,
        )
    batch_url = redirect.headers["location"]
    batch_id = batch_url.split("batch_id=")[-1]
    client.post(f"/acquisition-workspace/{batch_id}/select-all-eligible")
    run_response = client.post(
        f"/acquisition-workspace/{batch_id}/run-profit",
        data={"cost_profile": "standard", "use_cache": "on"},
        follow_redirects=False,
    )
    assert run_response.status_code == 303
    assert "profit_ok=1" in run_response.headers["location"]
    page = client.get(run_response.headers["location"])
    assert "利益分析が完了しました" in page.text
    assert "Profit" in page.text or "HOLD" in page.text or "BUY" in page.text or "利益" in page.text
    assert "データ取得方法" in page.text
    assert "比較" in page.text
    assert "理由:" in page.text
    assert "商品を見る" in page.text
    assert "総合評価" in page.text or "AI分析" in page.text


def test_run_profit_with_over_max_selected_returns_303_not_500(tmp_path: Path, monkeypatch) -> None:
    """Real-user path: select-all on large batch then 利益分析 must not Internal Server Error."""
    from marketplace.acquisition_workspace.profit_bridge import MAX_BATCH_CANDIDATES
    from marketplace.acquisition_workspace.workspace_service import AcquisitionWorkspaceService
    from app.storage.acquisition_workspace_repository import AcquisitionWorkspaceRepository
    from tests.test_acquisition_workspace_profit_bridge import (
        _distinct_wallet_listings,
        _fake_profit_run,
    )

    db_path = tmp_path / "overmax.db"
    service = AcquisitionWorkspaceService(AcquisitionWorkspaceRepository(database_path=db_path))
    batch = service.import_existing_listings(_distinct_wallet_listings(25), name="Over Max")
    service.select_all_eligible(batch.workspace_batch_id)

    monkeypatch.setattr(
        "profit_discovery.discovery_validation.batch_profit.pipeline.run_batch_profit",
        _fake_profit_run,
    )
    monkeypatch.setattr(
        "app.storage.batch_profit_repository.BatchProfitRepository.save_run",
        lambda self, run: None,
    )

    client = TestClient(create_app(database_path=db_path))
    response = client.post(
        f"/acquisition-workspace/{batch.workspace_batch_id}/run-profit",
        data={"cost_profile": "standard", "use_cache": "on"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert "profit_ok=1" in location
    assert "profit_capped=20" in location
    page = client.get(location)
    assert page.status_code == 200
    assert "Internal Server Error" not in page.text
    assert "利益分析が完了しました" in page.text
    assert "sticky-col-title" in page.text
    assert "page-acquisition-workspace" in page.text

    # Second click advances to the next unanalyzed tranche (not the same first 20).
    response2 = client.post(
        f"/acquisition-workspace/{batch.workspace_batch_id}/run-profit",
        data={"cost_profile": "standard", "use_cache": "on"},
        follow_redirects=False,
    )
    assert response2.status_code == 303
    assert "profit_ok=1" in response2.headers["location"]
    _, rows = service.get_batch(batch.workspace_batch_id)
    analyzed = sum(1 for item in rows if item.last_profit_checked_at)
    assert analyzed == 25
    assert analyzed > MAX_BATCH_CANDIDATES


def test_workspace_loads_when_saved_run_has_literal_none_money(tmp_path: Path, monkeypatch) -> None:
    """Live bug: GET workspace 500s after 利益分析 when cost_breakdown has purchase_price_jpy='None'."""
    import json
    from datetime import UTC, datetime
    from dataclasses import replace
    from decimal import Decimal

    from app.storage.acquisition_workspace_repository import AcquisitionWorkspaceRepository
    from app.storage.database import connect
    from marketplace.acquisition_workspace.analysis_version import PROFIT_ANALYSIS_VERSION
    from marketplace.acquisition_workspace.workspace_service import AcquisitionWorkspaceService
    from tests.test_acquisition_workspace_profit_bridge import (
        _distinct_wallet_listings,
        _fake_profit_run,
    )

    db_path = tmp_path / "none_trace.db"
    service = AcquisitionWorkspaceService(AcquisitionWorkspaceRepository(database_path=db_path))
    batch = service.import_existing_listings(_distinct_wallet_listings(25), name="None Trace")
    service.select_all_eligible(batch.workspace_batch_id)
    _, rows = service.get_batch(batch.workspace_batch_id)
    eligible = [
        item
        for item in rows
        if item.eligible_for_profit_check and not item.duplicate_of and item.quality_grade != "REJECTED"
    ]
    first_tranche = eligible[:20]
    poison_batch_id = "batch-poison-none"
    now = datetime.now(tz=UTC).isoformat()
    prior_profits = {item.candidate_id: Decimal("1000") for item in first_tranche}

    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO batch_runs (
                batch_id, started_at, completed_at, cost_profile, exchange_rate,
                total_candidates, processed_count, strong_candidate_count, review_count,
                hold_count, reject_count, failed_count, blocked_count,
                total_yahoo_requests, cache_hits, status, summary_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                poison_batch_id,
                now,
                now,
                "standard",
                "160",
                20,
                20,
                0,
                0,
                20,
                0,
                0,
                0,
                0,
                0,
                "completed",
                json.dumps(
                    {
                        "batch_id": poison_batch_id,
                        "started_at": now,
                        "completed_at": now,
                        "total_candidates": 20,
                        "processed_count": 20,
                        "strong_candidate_count": 0,
                        "review_count": 0,
                        "hold_count": 20,
                        "reject_count": 0,
                        "failed_count": 0,
                        "blocked_count": 0,
                        "total_yahoo_requests": 0,
                        "cache_hits": 0,
                        "exchange_rate": "160",
                        "cost_profile": "standard",
                        "status": "completed",
                        "import_errors": [],
                    },
                    ensure_ascii=False,
                ),
                now,
            ),
        )
        for rank, item in enumerate(first_tranche, start=1):
            payload = {
                "candidate": {
                    "candidate_id": item.candidate_id,
                    "title": item.title,
                    "brand": item.brand,
                    "category": item.category,
                    "detected_subtype": item.detected_subtype,
                    "detected_material": item.detected_material,
                    "condition": item.detected_condition,
                    "purchase_price": str(item.purchase_price),
                    "currency": item.currency,
                    "purchase_price_jpy": str(item.purchase_price_jpy),
                    "purchase_url": item.purchase_url,
                    "purchase_source": item.source_name,
                    "import_status": "OK",
                    "subtype_override": "",
                    "material_override": "",
                },
                "yahoo_queries": [],
                "yahoo_data_source": "FIXTURE",
                "yahoo_cache_retrieved_at": "",
                "yahoo_cache_age_hours": None,
                "raw_sample_count": 1,
                "accepted_comparable_count": 1,
                "rejected_sample_count": 0,
                "domestic": {
                    "raw_sample_count": 1,
                    "accepted_count": 1,
                    "rejected_count": 0,
                    "minimum_jpy": 100000,
                    "maximum_jpy": 100000,
                    "average_jpy": "100000",
                    "median_jpy": "100000",
                    "q1_jpy": 100000,
                    "q3_jpy": 100000,
                    "iqr_jpy": 0,
                    "outlier_count": 0,
                    "trimmed_average_jpy": None,
                    "recommended_selling_estimate_jpy": "100000",
                    "reliability": "MEDIUM",
                },
                "estimated_costs": {
                    "exchange_rate": "160 JPY/USD",
                    "international_shipping_jpy": "0",
                    "forwarding_fee_jpy": "0",
                    "import_duty_jpy": "0",
                    "import_tax_jpy": "0",
                    "payment_fee_jpy": "0",
                    "domestic_platform_fee_jpy": "0",
                    "domestic_shipping_jpy": "0",
                    "inspection_or_repair_reserve_jpy": "0",
                    "miscellaneous_cost_jpy": "0",
                    "total_additional_costs_jpy": "0",
                    "net_profit_complete": False,
                    "unconfigured_fields": [],
                },
                "gross_estimated_profit": "1000",
                "net_estimated_profit": None,
                "profit_margin": "1",
                "net_profit_margin": None,
                "roi": "1",
                "net_roi": None,
                "engine_decision": "HOLD",
                "batch_decision": "HOLD",
                "data_status": "FIXTURE",
                "verification_complete": False,
                "retrieved_at": now,
                "failure_reason": "",
                "comparable_warning": "",
                "warnings": [],
                "diagnostics": "{}",
                "accepted_comparables_display": "",
                "rejected_samples_display": "",
                "yahoo_best_title": "",
                "yahoo_best_price_jpy": 0,
                "yahoo_best_url": "",
                "yahoo_best_score": 0,
                "yahoo_best_attributes": "",
                "yahoo_best_condition": "",
                "yahoo_marketplace": "",
                "rank": rank,
                "operational_trace": {
                    "profit": {
                        "cost_breakdown": {
                            "source": "ProfitCalculator/ImportCostEngine",
                            "purchase_price_jpy": "None",
                            "international_shipping_jpy": "None",
                            "domestic_shipping_jpy": "0",
                            "payment_fee_jpy": "0",
                        }
                    }
                },
            }
            connection.execute(
                "INSERT INTO batch_profit_results (batch_id, candidate_id, rank, result_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (poison_batch_id, item.candidate_id, rank, json.dumps(payload, ensure_ascii=False), now),
            )
        connection.commit()

    for item in first_tranche:
        service._repo.update_candidate(
            replace(
                item,
                last_profit_batch_id=poison_batch_id,
                last_profit_checked_at=now,
                last_gross_profit=Decimal("1000"),
                last_net_profit=None,
                last_decision="HOLD",
                selected_for_profit_check=True,
                discovery_metadata=replace(
                    item.discovery_metadata,
                    profit_analysis_version=PROFIT_ANALYSIS_VERSION,
                ),
            )
        )

    client = TestClient(create_app(database_path=db_path))
    page_poisoned = client.get(f"/acquisition-workspace?batch_id={batch.workspace_batch_id}")
    assert page_poisoned.status_code == 200
    assert "Internal Server Error" not in page_poisoned.text

    monkeypatch.setattr(
        "profit_discovery.discovery_validation.batch_profit.pipeline.run_batch_profit",
        _fake_profit_run,
    )
    monkeypatch.setattr(
        "app.storage.batch_profit_repository.BatchProfitRepository.save_run",
        lambda self, run: None,
    )

    second = client.post(
        f"/acquisition-workspace/{batch.workspace_batch_id}/run-profit",
        data={"cost_profile": "standard", "use_cache": "on"},
        follow_redirects=False,
    )
    assert second.status_code == 303
    assert "profit_ok=1" in second.headers["location"]
    page2 = client.get(second.headers["location"])
    assert page2.status_code == 200
    assert "Internal Server Error" not in page2.text

    _, after = service.get_batch(batch.workspace_batch_id)
    analyzed_after = sum(1 for item in after if item.last_profit_checked_at)
    assert analyzed_after == 25
    for item in after:
        if item.candidate_id in prior_profits:
            assert item.last_gross_profit == prior_profits[item.candidate_id]
