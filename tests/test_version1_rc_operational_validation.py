"""Deterministic fixture-only tests for Version 1.0 RC operational validation."""

from __future__ import annotations

import json
from pathlib import Path

from profit_discovery.discovery_validation.version1_rc_operational import (
    MARKETPLACE_CONFIG,
    run_validation,
    write_reports,
)


def test_version1_rc_fixture_validation_runs_all_four_independently(tmp_path: Path, monkeypatch) -> None:
    report = run_validation(limit=3, enable_live=False, seed=1)
    assert report["aggregate"]["system_health"]["marketplaces_ok"] == 4
    assert len(report["marketplaces"]) == 4
    names = [item["marketplace"] for item in report["marketplaces"]]
    assert names == list(MARKETPLACE_CONFIG.keys())
    assert report["aggregate"]["system_health"]["overseas_never_selected_as_domestic"] is True
    assert report["aggregate"]["system_health"]["url_traceability_ok"] is True
    assert report["readiness"]["recommendation"] in {
        "Ready for Version 1.0",
        "Minor fixes recommended",
        "Not ready",
    }

    out_json = tmp_path / "version1_rc_operational_report.json"
    out_md = tmp_path / "version1_rc_summary.md"
    monkeypatch.setattr(
        "profit_discovery.discovery_validation.version1_rc_operational.OUTPUT_JSON",
        out_json,
    )
    monkeypatch.setattr(
        "profit_discovery.discovery_validation.version1_rc_operational.OUTPUT_MD",
        out_md,
    )
    json_path, md_path = write_reports(report)
    assert json_path.exists()
    assert md_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "version1-rc"
    text = md_path.read_text(encoding="utf-8")
    assert "Overall system health" in text
    assert "Fashionphile" in text
    assert "Vestiaire Collective" in text


def test_version1_rc_one_marketplace_failure_does_not_stop_others(monkeypatch) -> None:
    original = MARKETPLACE_CONFIG["Rebag"]["parser"]

    def _boom(_html, **_kwargs):
        raise RuntimeError("simulated rebag failure")

    monkeypatch.setitem(MARKETPLACE_CONFIG["Rebag"], "parser", _boom)
    try:
        report = run_validation(limit=2, enable_live=False, seed=2)
    finally:
        monkeypatch.setitem(MARKETPLACE_CONFIG["Rebag"], "parser", original)

    by_name = {item["marketplace"]: item for item in report["marketplaces"]}
    assert by_name["Rebag"]["status"] == "FAILED"
    assert by_name["Fashionphile"]["status"] == "OK"
    assert by_name["The RealReal"]["status"] == "OK"
    assert by_name["Vestiaire Collective"]["status"] == "OK"
