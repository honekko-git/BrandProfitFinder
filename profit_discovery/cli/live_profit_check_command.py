"""CLI entry point for controlled live profit checks."""

from __future__ import annotations

import argparse
import sys
from typing import TextIO

from profit_discovery.discovery_validation.controlled_live_verification import (
    build_controlled_live_verifications,
)


def build_live_profit_check_parser() -> argparse.ArgumentParser:
    """Build parser for controlled live profit check command."""
    parser = argparse.ArgumentParser(
        prog="live-profit-check",
        description="Run one controlled live Fashionphile -> Yahoo Auction profit check.",
    )
    parser.add_argument("--brand", default="Chanel", help="Brand (Chanel only)")
    parser.add_argument("--category", default="Wallet", help="Category (Wallet only)")
    parser.add_argument("--purchase-limit", type=int, default=10, help="Max Fashionphile listings")
    parser.add_argument("--sold-limit", type=int, default=20, help="Max Yahoo sold samples per item")
    return parser


def run_live_profit_check_command(
    argv: list[str] | None = None,
    *,
    output: TextIO | None = None,
) -> int:
    """Execute one controlled live profit check and print summary."""
    stream = output or sys.stdout
    args = build_live_profit_check_parser().parse_args(argv)
    results, blocking_reason = build_controlled_live_verifications(
        brand=args.brand,
        category=args.category,
        purchase_limit=args.purchase_limit,
        sold_limit=args.sold_limit,
    )

    if blocking_reason:
        stream.write(f"Status: BLOCKED ({blocking_reason})\n")
        return 1

    if not results:
        stream.write("Status: NO_RESULTS\n")
        return 1

    top = results[0]
    stream.write(f"Acquired purchase count: {len(results)}\n")
    stream.write(f"Yahoo matched sample count: {top.yahoo_matched_samples}\n")
    stream.write(f"Status: {top.acquisition_status} / data_status={top.data_status}\n")
    stream.write(f"Top estimated profit: {top.estimated_profit} JPY\n")
    stream.write(f"Decision: {top.decision}\n")
    stream.write(f"Fashionphile URL: {top.fashionphile_url}\n")
    if top.blocking_reason:
        stream.write(f"Blocking reason: {top.blocking_reason}\n")
    return 0


def run_live_profit_check_cli(argv: list[str] | None = None) -> int:
    """CLI wrapper."""
    return run_live_profit_check_command(argv)
