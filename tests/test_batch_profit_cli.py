"""Tests for batch profit CLI."""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

from profit_discovery.cli.batch_profit_command import run_batch_profit_command

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "batch_profit"
YAHOO_HTML = (Path(__file__).resolve().parent / "fixtures" / "browser_acquisition" / "yahoo_live_ja.html").read_text(
    encoding="utf-8"
)


def test_cli_command_output(tmp_path: Path, monkeypatch) -> None:
    def _fake_run_batch_profit(candidates, **kwargs):
        kwargs["html_by_query"] = {"シャネル クラシック 財布": YAHOO_HTML}
        from profit_discovery.discovery_validation.batch_profit.pipeline import run_batch_profit as real_run

        return real_run(candidates, **kwargs)

    monkeypatch.setattr("profit_discovery.cli.batch_profit_command.run_batch_profit", _fake_run_batch_profit)
    stream = StringIO()
    exit_code = run_batch_profit_command(
        ["--csv", str(FIXTURES / "candidates_valid.csv"), "--limit", "2", "--cost-profile", "standard"],
        output=stream,
    )
    output = stream.getvalue()
    assert exit_code == 0
    assert "Batch ID" in output
    assert "Processed" in output


def test_cli_json_and_csv_export(tmp_path: Path, monkeypatch) -> None:
    def _fake_run_batch_profit(candidates, **kwargs):
        kwargs["html_by_query"] = {"シャネル クラシック 財布": YAHOO_HTML}
        from profit_discovery.discovery_validation.batch_profit.pipeline import run_batch_profit as real_run

        return real_run(candidates, **kwargs)

    monkeypatch.setattr("profit_discovery.cli.batch_profit_command.run_batch_profit", _fake_run_batch_profit)
    json_path = tmp_path / "output" / "batch.json"
    csv_path = tmp_path / "output" / "batch.csv"
    stream = StringIO()
    exit_code = run_batch_profit_command(
        [
            "--csv",
            str(FIXTURES / "candidates_valid.csv"),
            "--limit",
            "1",
            "--output-json",
            str(json_path),
            "--output-csv",
            str(csv_path),
        ],
        output=stream,
    )
    assert exit_code == 0
    assert json_path.exists()
    assert csv_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["results"]


def test_cli_partial_import_errors(tmp_path: Path) -> None:
    stream = StringIO()
    exit_code = run_batch_profit_command(
        ["--csv", str(FIXTURES / "candidates_invalid.csv"), "--limit", "5"],
        output=stream,
    )
    assert exit_code == 0
    assert "Candidate error" in stream.getvalue() or "Processed" in stream.getvalue()
