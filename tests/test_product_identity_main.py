"""CLI tests for product identity demo."""

import sys
from io import StringIO

import main


def test_identity_demo_flag_detected() -> None:
    assert main.is_identity_demo_requested(["--identity-demo"]) is True
    assert main.is_identity_demo_requested(["--demo-identity"]) is True


def test_cli_help_documents_identity_demo() -> None:
    parser = main.build_cli_parser()
    buffer = StringIO()
    parser.print_help(file=buffer)
    help_text = buffer.getvalue()
    assert "--identity-demo" in help_text
    assert "--demo-identity" in help_text


def test_identity_demo_runs() -> None:
    from product_identity.demo import run_identity_demo

    counts = run_identity_demo()
    assert counts["total"] == 10
    assert counts["MATCH"] >= 1
