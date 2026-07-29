"""Discovery CLI command wiring."""

from profit_discovery.cli.discovery_command import (
    DiscoveryCommandOptions,
    build_discovery_parser,
    build_production_discovery_pipeline,
    export_discovery_report,
    parse_brands,
    run_discovery_cli,
    run_discovery_command,
)
from profit_discovery.cli.discovery_output import (
    DiscoveryDisplaySummary,
    build_display_summary,
    format_demand_opportunity_ranking,
    format_discovery_summary,
    format_export_message,
    format_top_buy_candidates,
    render_discovery_run,
    render_showcase,
)

__all__ = [
    "DiscoveryCommandOptions",
    "DiscoveryDisplaySummary",
    "build_discovery_parser",
    "build_display_summary",
    "build_production_discovery_pipeline",
    "export_discovery_report",
    "format_demand_opportunity_ranking",
    "format_discovery_summary",
    "format_export_message",
    "format_top_buy_candidates",
    "parse_brands",
    "render_discovery_run",
    "render_showcase",
    "run_discovery_cli",
    "run_discovery_command",
]
