"""Showcase dashboard export helpers for discovery CLI reports."""

from __future__ import annotations

from decimal import Decimal

import pandas as pd
from openpyxl import load_workbook

from excel.formatter import apply_sheet_layout
from profit_discovery.showcase.formatter import ShowcaseFormatter
from profit_discovery.showcase.models import ShowcaseOpportunity

SHEET_SHOWCASE = "Showcase"

SHOWCASE_COLUMNS: tuple[str, ...] = (
    "Rank",
    "Brand",
    "Product",
    "Supplier",
    "Profit",
    "ROI",
    "Demand Score",
    "Opportunity Score",
    "Decision",
)


def showcase_opportunities_to_rows(opportunities: list[ShowcaseOpportunity]) -> list[dict[str, object]]:
    """Convert showcase opportunities into flat export rows."""
    rows: list[dict[str, object]] = []
    for item in opportunities:
        rows.append(
            {
                "Rank": item.rank,
                "Brand": item.brand,
                "Product": item.product_name,
                "Supplier": item.supplier,
                "Profit": _format_export_jpy(item.profit_jpy),
                "ROI": _format_export_percent(item.roi),
                "Demand Score": round(item.demand_score, 1),
                "Opportunity Score": round(item.opportunity_score, 1),
                "Decision": item.decision,
            }
        )
    return rows


def append_showcase_sheet(
    workbook_path,
    opportunities: list[ShowcaseOpportunity],
) -> None:
    """Append the Showcase sheet to an existing discovery workbook."""
    if not opportunities:
        return

    rows = showcase_opportunities_to_rows(opportunities)
    with pd.ExcelWriter(
        workbook_path,
        engine="openpyxl",
        mode="a",
        if_sheet_exists="replace",
    ) as writer:
        pd.DataFrame(rows, columns=list(SHOWCASE_COLUMNS)).to_excel(
            writer,
            index=False,
            sheet_name=SHEET_SHOWCASE,
        )

    workbook = load_workbook(workbook_path)
    if SHEET_SHOWCASE in workbook.sheetnames:
        apply_sheet_layout(workbook[SHEET_SHOWCASE], len(SHOWCASE_COLUMNS))
        workbook.save(workbook_path)


def build_showcase_opportunities_from_ranking(
    opportunities,
) -> list[ShowcaseOpportunity]:
    """Build showcase rows from demand-integrated ranking results."""
    return list(ShowcaseFormatter().to_showcase_opportunities(opportunities))


def _format_export_jpy(value: Decimal | None) -> str:
    if value is None:
        return "N/A"
    return f"{int(value):,} JPY"


def _format_export_percent(value: Decimal | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.1f}%"
