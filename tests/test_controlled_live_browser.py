"""Browser tests for controlled live validation UI."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.controlled_live_pipeline import run_controlled_live_verification_search
from app.main import create_app
from app.store import ValidationResultStore

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "browser_acquisition"


def test_controlled_live_browser_shows_result_fields(monkeypatch) -> None:
    purchase_html = (FIXTURES / "fashionphile_search_results.html").read_text(encoding="utf-8")
    yahoo_html = (FIXTURES / "yahoo_sold_results.html").read_text(encoding="utf-8")

    def _fake_execute(store, **kwargs):
        result = run_controlled_live_verification_search(
            brand="Chanel",
            category="Wallet",
            purchase_html=purchase_html,
            yahoo_html_by_query={
                "black caviar chanel classic wallet": yahoo_html,
                "black caviar chanel quilted wallet zip": yahoo_html,
            },
        )
        store.save(result.snapshot)
        return result

    store = ValidationResultStore()
    client = TestClient(create_app(validation_store=store))
    monkeypatch.setattr("app.routes.execute_controlled_live_verification_search", _fake_execute)

    response = client.post(
        "/validation/controlled-live",
        data={"brand": "Chanel", "category": "Wallet"},
    )

    assert response.status_code == 200
    assert "CONTROLLED LIVE 利益結果" in response.text
    assert "Controlled Live確認を実行" in response.text
    assert "マッチングスコア" in response.text
    assert "検証完了" in response.text
    assert "データ状態:" in response.text

    snapshot = store.get()
    assert snapshot is not None
    assert snapshot.verification_mode == "CONTROLLED_LIVE"
    row = snapshot.controlled_live_results[0]
    assert row.fashionphile_url in response.text
    assert row.decision.startswith("PROVISIONAL") or row.decision in {"BUY", "HOLD", "PASS"}


def test_controlled_live_browser_shows_blocked_reason(monkeypatch) -> None:
    def _fake_execute(store, **kwargs):
        snapshot_store = store
        from app.store import ValidationSearchSnapshot

        snapshot_store.save(
            ValidationSearchSnapshot(
                brand="Chanel",
                category="Wallet",
                market_mode="CONTROLLED_LIVE",
                verification_mode="CONTROLLED_LIVE",
                blocking_reason="SELECTOR_NOT_FOUND",
            )
        )
        from app.controlled_live_pipeline import ControlledLivePipelineResult

        return ControlledLivePipelineResult(
            snapshot=snapshot_store.get(),
            results=[],
            blocking_reason="SELECTOR_NOT_FOUND",
            result_count=0,
        )

    store = ValidationResultStore()
    client = TestClient(create_app(validation_store=store))
    monkeypatch.setattr("app.routes.execute_controlled_live_verification_search", _fake_execute)

    response = client.post(
        "/validation/controlled-live",
        data={"brand": "Chanel", "category": "Wallet"},
    )
    assert response.status_code == 200
    assert "ブロック: SELECTOR_NOT_FOUND" in response.text
