"""Full v3 continuous reanalysis for workspace validation (no feature changes)."""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.storage.acquisition_workspace_repository import AcquisitionWorkspaceRepository  # noqa: E402
from marketplace.acquisition_workspace.analysis_version import (  # noqa: E402
    PROFIT_ANALYSIS_VERSION,
    is_profit_analysis_current,
)
from marketplace.acquisition_workspace.continuous_analysis import (  # noqa: E402
    ContinuousAnalysisController,
)
from marketplace.acquisition_workspace.workspace_service import AcquisitionWorkspaceService  # noqa: E402

BATCH = "ws-20260731183118-b673ef"
DB = ROOT / "data" / "brand_profit.db"
OUT = ROOT / "output" / "_v3_replay_progress.json"


def _stats(service: AcquisitionWorkspaceService) -> dict:
    _, candidates = service._repo.get_batch(BATCH)
    eligible = [
        c
        for c in candidates
        if c.eligible_for_profit_check and not c.duplicate_of and c.quality_grade != "REJECTED"
    ]
    analyzed = [c for c in eligible if is_profit_analysis_current(c)]
    return {
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "analysis_version": PROFIT_ANALYSIS_VERSION,
        "total": len(candidates),
        "eligible": len(eligible),
        "analyzed_current": len(analyzed),
        "remaining": len(eligible) - len(analyzed),
    }


def main() -> None:
    service = AcquisitionWorkspaceService(AcquisitionWorkspaceRepository(database_path=DB))
    controller = ContinuousAnalysisController()
    started = time.time()
    print(json.dumps({"event": "start", **_stats(service)}, ensure_ascii=False))

    progress = controller.start(
        BATCH,
        service,
        cost_profile_name="standard",
        use_cache=True,
        sleep_between_batches=0.5,
    )
    print(json.dumps({"event": "started", "status": progress.status, "remaining": progress.remaining}, ensure_ascii=False))

    last_write = 0.0
    while True:
        prog = controller.get_progress(BATCH, service)
        stats = _stats(service)
        payload = {
            "event": "progress",
            "status": prog.status,
            "batches_completed": prog.batches_completed,
            "failed": prog.failed,
            "error_message": prog.error_message,
            "elapsed_sec": round(time.time() - started, 1),
            **stats,
        }
        now = time.time()
        if now - last_write >= 15 or prog.status in {"complete", "error", "stopped"}:
            OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(payload, ensure_ascii=False))
            last_write = now

        if prog.status == "complete" and stats["remaining"] == 0:
            break
        if prog.status in {"error", "stopped"}:
            raise SystemExit(f"continuous analysis ended with status={prog.status}: {prog.error_message}")
        if prog.status in {"idle", "complete"} and stats["remaining"] > 0:
            controller.start(BATCH, service, cost_profile_name="standard", use_cache=True, sleep_between_batches=0.5)
        if time.time() - started > 6 * 3600:
            raise SystemExit("timeout after 6 hours")
        time.sleep(10)

    final = {"event": "complete", "elapsed_sec": round(time.time() - started, 1), **_stats(service)}
    OUT.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(final, ensure_ascii=False))


if __name__ == "__main__":
    main()
