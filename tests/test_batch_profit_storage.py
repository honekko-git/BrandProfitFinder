"""Tests for batch profit SQLite storage."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from app.storage.batch_profit_repository import BatchProfitRepository
from profit_discovery.discovery_validation.batch_profit.candidate_import import load_batch_candidates_from_csv
from profit_discovery.discovery_validation.batch_profit.costs import default_cost_profiles
from profit_discovery.discovery_validation.batch_profit.pipeline import run_batch_profit

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "batch_profit"
YAHOO_HTML = (Path(__file__).resolve().parent / "fixtures" / "browser_acquisition" / "yahoo_live_ja.html").read_text(
    encoding="utf-8"
)


def test_batch_save_read_and_history(tmp_path: Path) -> None:
    db_path = tmp_path / "batch.db"
    repo = BatchProfitRepository(database_path=db_path)
    imported = load_batch_candidates_from_csv(FIXTURES / "candidates_valid.csv", limit=2)
    run = run_batch_profit(
        imported.candidates,
        cost_profile=default_cost_profiles()["standard"],
        use_cache=False,
        html_by_query={"シャネル クラシック 財布": YAHOO_HTML},
    )
    repo.save_run(run)
    loaded = repo.get_run(run.summary.batch_id)
    assert loaded is not None
    assert loaded.summary.batch_id == run.summary.batch_id
    assert len(loaded.results) == len(run.results)
    history = repo.list_runs(limit=5)
    assert history
    assert history[0].batch_id == run.summary.batch_id


def test_delete_batch(tmp_path: Path) -> None:
    db_path = tmp_path / "batch.db"
    repo = BatchProfitRepository(database_path=db_path)
    imported = load_batch_candidates_from_csv(FIXTURES / "candidates_valid.csv", limit=1)
    run = run_batch_profit(
        imported.candidates[:1],
        cost_profile=default_cost_profiles()["standard"],
        use_cache=False,
        html_by_query={"シャネル クラシック 財布": YAHOO_HTML},
    )
    repo.save_run(run)
    repo.delete_run(run.summary.batch_id)
    assert repo.get_run(run.summary.batch_id) is None


def test_existing_db_compatibility(tmp_path: Path) -> None:
    from app.storage.database import connect

    db_path = tmp_path / "brand_profit.db"
    with connect(db_path):
        pass
    repo = BatchProfitRepository(database_path=db_path)
    imported = load_batch_candidates_from_csv(FIXTURES / "candidates_valid.csv", limit=1)
    run = run_batch_profit(
        imported.candidates[:1],
        cost_profile=default_cost_profiles()["standard"],
        use_cache=False,
        html_by_query={"シャネル クラシック 財布": YAHOO_HTML},
    )
    repo.save_run(run)
    assert repo.get_run(run.summary.batch_id) is not None


def test_decode_decimal_skips_literal_none_string(capsys) -> None:
    """Exact live failure: operational_trace cost_breakdown.purchase_price_jpy == 'None'."""
    from app.storage.batch_profit_repository import _decode_decimal, _decode_decimals

    # Exact cost_breakdown object from batch-20260731192635-d55770 / ac-e5f0e54593e6
    cost_breakdown = {
        "source": "ProfitCalculator/ImportCostEngine",
        "purchase_price_jpy": "None",
        "international_shipping_jpy": "0",
        "customs_duty_jpy": "0",
        "import_tax_jpy": "0",
        "domestic_shipping_jpy": "0",
        "marketplace_fee_jpy": "0",
        "other_costs_jpy": "0",
        "total_cost_jpy": "0",
        "profit_jpy": "0",
        "formula": "sale - total_cost_jpy - marketplace_fee_jpy",
        "config_source": "ProfitConfig defaults via MarketplaceConfiguration.from_profit_config",
    }

    assert _decode_decimal("purchase_price_jpy", "None") is None
    captured = capsys.readouterr().out
    assert "field name=" in captured
    assert "purchase_price_jpy" in captured
    assert "'None'" in captured
    assert "str" in captured

    decoded = _decode_decimals({"operational_trace": {"profit": {"cost_breakdown": cost_breakdown}}})
    breakdown = decoded["operational_trace"]["profit"]["cost_breakdown"]
    assert breakdown["purchase_price_jpy"] is None
    assert breakdown["international_shipping_jpy"] == Decimal("0")
    # Non-money keys must remain untouched (not forced through Decimal).
    assert breakdown["source"] == "ProfitCalculator/ImportCostEngine"
    assert breakdown["formula"] == "sale - total_cost_jpy - marketplace_fee_jpy"
    assert breakdown["customs_duty_jpy"] == "0"  # not in money decode set; left as stored

    # Labels / empty / nested must never raise.
    assert _decode_decimal("roi", "HOLD") is None
    assert _decode_decimal("roi", "HIGH") is None
    assert _decode_decimal("roi", "LOW") is None
    assert _decode_decimal("roi", "REVIEW") is None
    assert _decode_decimal("purchase_price_jpy", "") is None
    assert _decode_decimal("purchase_price_jpy", None) is None
    assert _decode_decimal("purchase_price_jpy", {"nested": 1}) is None
    assert _decode_decimal("purchase_price_jpy", ["1"]) is None


def test_trace_money_serializes_missing_as_json_null_not_string_none() -> None:
    """Write path audit: never str(None); missing amounts become JSON null."""
    import json

    from profit_discovery.discovery_validation.batch_profit.pipeline import _trace_money

    # Failed PriceResult leaves purchase_price_jpy as None (attribute present).
    assert _trace_money(None, fallback=Decimal("111200")) == "111200"
    assert _trace_money(None, fallback=None) is None
    assert _trace_money(Decimal("0")) == "0"

    payload = {
        "purchase_price_jpy": _trace_money(None, fallback=None),
        "international_shipping_jpy": _trace_money(Decimal("0")),
    }
    encoded = json.dumps(payload, ensure_ascii=False)
    assert '"purchase_price_jpy": null' in encoded
    assert '"None"' not in encoded
    assert '"international_shipping_jpy": "0"' in encoded


def test_get_run_tolerates_literal_none_money_strings(tmp_path: Path) -> None:
    """Regression: failed calc wrote str(None) into operational_trace cost_breakdown."""
    import json
    from datetime import UTC, datetime

    from app.storage.database import connect

    db_path = tmp_path / "none_money.db"
    batch_id = "batch-none-money"
    now = datetime.now(tz=UTC).isoformat()
    # Exact live cost_breakdown payload that previously raised ConversionSyntax.
    exact_cost_breakdown = {
        "source": "ProfitCalculator/ImportCostEngine",
        "purchase_price_jpy": "None",
        "international_shipping_jpy": "0",
        "customs_duty_jpy": "0",
        "import_tax_jpy": "0",
        "domestic_shipping_jpy": "0",
        "marketplace_fee_jpy": "0",
        "other_costs_jpy": "0",
        "total_cost_jpy": "0",
        "profit_jpy": "0",
        "formula": "sale - total_cost_jpy - marketplace_fee_jpy",
        "config_source": "ProfitConfig defaults via MarketplaceConfiguration.from_profit_config",
    }
    result_payload = {
        "candidate": {
            "candidate_id": "ac-e5f0e54593e6",
            "title": "Test",
            "brand": "Chanel",
            "category": "Wallet",
            "detected_subtype": "",
            "detected_material": "",
            "condition": "",
            "purchase_price": "100",
            "currency": "USD",
            "purchase_price_jpy": "16000",
            "purchase_url": "https://example.com/p/1",
            "purchase_source": "Fashionphile",
            "import_status": "OK",
            "subtype_override": "",
            "material_override": "",
        },
        "yahoo_queries": [],
        "yahoo_data_source": "FIXTURE",
        "yahoo_cache_retrieved_at": "",
        "yahoo_cache_age_hours": None,
        "raw_sample_count": 0,
        "accepted_comparable_count": 0,
        "rejected_sample_count": 0,
        "domestic": {
            "raw_sample_count": 0,
            "accepted_count": 0,
            "rejected_count": 0,
            "minimum_jpy": 0,
            "maximum_jpy": 0,
            "average_jpy": "0",
            "median_jpy": "0",
            "q1_jpy": 0,
            "q3_jpy": 0,
            "iqr_jpy": 0,
            "outlier_count": 0,
            "trimmed_average_jpy": None,
            "recommended_selling_estimate_jpy": "0",
            "reliability": "LOW",
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
        "gross_estimated_profit": "0",
        "net_estimated_profit": None,
        "profit_margin": "0",
        "net_profit_margin": None,
        "roi": "0",
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
        "rank": 1,
        "operational_trace": {
            "profit": {
                "cost_breakdown": exact_cost_breakdown,
            }
        },
    }
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
                batch_id,
                now,
                now,
                "standard",
                "160",
                1,
                1,
                0,
                0,
                1,
                0,
                0,
                0,
                0,
                0,
                "completed",
                json.dumps(
                    {
                        "batch_id": batch_id,
                        "started_at": now,
                        "completed_at": now,
                        "total_candidates": 1,
                        "processed_count": 1,
                        "strong_candidate_count": 0,
                        "review_count": 0,
                        "hold_count": 1,
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
        connection.execute(
            "INSERT INTO batch_profit_results (batch_id, candidate_id, rank, result_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (batch_id, "ac-e5f0e54593e6", 1, json.dumps(result_payload, ensure_ascii=False), now),
        )
        connection.commit()

    loaded = BatchProfitRepository(database_path=db_path).get_run(batch_id)
    assert loaded is not None
    assert loaded.results[0].candidate.candidate_id == "ac-e5f0e54593e6"
    breakdown = loaded.results[0].operational_trace["profit"]["cost_breakdown"]
    assert breakdown["purchase_price_jpy"] is None
