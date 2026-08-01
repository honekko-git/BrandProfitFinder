"""Profit analysis versioning for re-running outdated candidate results.

Stored on DiscoveryMetadata (candidate_json) — no DB schema migration.
Does not change ProfitCalculator, ranking formulas, matching, FX, or acquisition.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Bump when profit-analysis rules change (comparable quality, new-market, etc.).
# v3: domestic query-generation contract + persist queries on acquisition failure.
PROFIT_ANALYSIS_VERSION = "v3"

REANALYSIS_REASON = "分析ルール更新"
STATUS_ANALYZED = "分析済み"
STATUS_NEEDS_REANALYSIS = "再分析対象"
STATUS_PENDING = "未分析"


@dataclass(frozen=True)
class AnalysisStatusView:
    label: str
    reason: str
    needs_reanalysis: bool
    is_current: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "reason": self.reason,
            "needs_reanalysis": self.needs_reanalysis,
            "is_current": self.is_current,
        }


def stored_analysis_version(candidate: Any) -> str:
    metadata = getattr(candidate, "discovery_metadata", None)
    if metadata is None:
        return ""
    return str(getattr(metadata, "profit_analysis_version", "") or "").strip()


def has_profit_check_result(candidate: Any) -> bool:
    """True when a prior profit run wrote a result marker on the candidate."""
    if getattr(candidate, "last_profit_checked_at", None):
        return True
    if getattr(candidate, "last_profit_batch_id", None):
        return True
    if getattr(candidate, "last_gross_profit", None) is not None:
        return True
    if getattr(candidate, "last_net_profit", None) is not None:
        return True
    return False


def is_profit_analysis_current(candidate: Any) -> bool:
    """Completed for selection: has profit result AND version matches current."""
    if not has_profit_check_result(candidate):
        return False
    return stored_analysis_version(candidate) == PROFIT_ANALYSIS_VERSION


def needs_profit_reanalysis(candidate: Any) -> bool:
    return has_profit_check_result(candidate) and not is_profit_analysis_current(candidate)


def analysis_status_view(candidate: Any) -> AnalysisStatusView:
    if is_profit_analysis_current(candidate):
        return AnalysisStatusView(
            label=STATUS_ANALYZED,
            reason="",
            needs_reanalysis=False,
            is_current=True,
        )
    if needs_profit_reanalysis(candidate):
        return AnalysisStatusView(
            label=STATUS_NEEDS_REANALYSIS,
            reason=REANALYSIS_REASON,
            needs_reanalysis=True,
            is_current=False,
        )
    return AnalysisStatusView(
        label=STATUS_PENDING,
        reason="",
        needs_reanalysis=False,
        is_current=False,
    )
