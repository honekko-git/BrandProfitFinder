"""Tests for profit intelligence CLI integration."""

from io import StringIO
from pathlib import Path
from unittest.mock import patch

import main


def test_profit_intelligence_flag_detected() -> None:
    assert main.is_profit_intelligence_requested(["--profit-intelligence"]) is True
    assert main.is_profit_intelligence_requested(["--ai-score"]) is True
    assert main.is_profit_intelligence_requested([]) is False


def test_cli_parser_maps_alias_to_same_destination() -> None:
    parser = main.build_cli_parser()
    args = parser.parse_args(["--profit-intelligence"])
    assert args.profit_intelligence is True
    alias_args = parser.parse_args(["--ai-score"])
    assert alias_args.profit_intelligence is True


def test_cli_help_describes_deterministic_scoring() -> None:
    parser = main.build_cli_parser()
    buffer = StringIO()
    parser.print_help(file=buffer)
    help_text = buffer.getvalue().lower()
    assert "profit intelligence" in help_text
    assert "deterministic" in help_text
    assert "rule-based" in help_text
    assert "llm" not in help_text or "not llm" in help_text


def test_run_accepts_profit_intelligence_parameter() -> None:
    with patch.object(main, "run_phase3") as run_phase3:
        run_phase3.return_value = Path("out.xlsx")
        main.run(profit_intelligence=True)
        run_phase3.assert_called_once_with(
            marketplace_name=None,
            profit_intelligence=True,
        )
