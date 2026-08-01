"""Live continuous-analysis smoke check against the Fashionphile workspace."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:8000"
BATCH = "ws-20260731183118-b673ef"
OUT = Path("output/continuous_profit_analysis_verification.json")


def call(method: str, path: str, payload=None):
    from urllib.error import HTTPError

    data = None if payload is None else json.dumps(payload).encode()
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urlopen(req, timeout=120) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"raw": body}
        return exc.code, parsed


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    page = urlopen(f"{BASE}/acquisition-workspace?batch_id={BATCH}", timeout=60).read().decode(
        "utf-8", "replace"
    )
    ui = {
        "has_continuous_button": "連続分析" in page and "data-profit-continuous" in page,
        "has_manual_button": "利益分析" in page,
        "has_panel": "continuous-profit-panel" in page,
    }
    print("UI", ui)

    _st, before = call("GET", f"/acquisition-workspace/{BATCH}/continuous-profit/status")
    print("BEFORE", before)

    events = []
    _st, started = call(
        "POST",
        f"/acquisition-workspace/{BATCH}/continuous-profit/start",
        {"cost_profile": "standard", "use_cache": True},
    )
    events.append({"event": "start", "body": started})
    print("START", started.get("status"), started.get("analyzed"), started.get("remaining"))

    # Concurrent start should be busy.
    _st2, busy = call(
        "POST",
        f"/acquisition-workspace/{BATCH}/continuous-profit/start",
        {"cost_profile": "standard", "use_cache": True},
    )
    events.append({"event": "double_start", "http_like": _st2, "body": busy})
    print("BUSY", busy.get("status"), busy.get("user_message"))

    # Observe until analyzed advances by at least one tranche, or timeout.
    baseline = before.get("analyzed") or 0
    observed = []
    deadline = time.time() + 900  # up to 15 min for one live tranche
    while time.time() < deadline:
        _st, progress = call("GET", f"/acquisition-workspace/{BATCH}/continuous-profit/status")
        observed.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "status": progress.get("status"),
                "analyzed": progress.get("analyzed"),
                "remaining": progress.get("remaining"),
                "detail": progress.get("detail_message"),
            }
        )
        print(
            "POLL",
            progress.get("status"),
            progress.get("analyzed"),
            progress.get("remaining"),
            progress.get("detail_message"),
        )
        if (progress.get("analyzed") or 0) >= baseline + 20:
            break
        if progress.get("status") in {"complete", "error", "stopped"}:
            break
        time.sleep(5)

    _st, stopped = call("POST", f"/acquisition-workspace/{BATCH}/continuous-profit/stop")
    events.append({"event": "stop", "body": stopped})
    print("STOP", stopped.get("status"), stopped.get("analyzed"), stopped.get("remaining"))

    # Wait until stopped/complete after current tranche finishes.
    end_deadline = time.time() + 900
    final = stopped
    while time.time() < end_deadline:
        _st, final = call("GET", f"/acquisition-workspace/{BATCH}/continuous-profit/status")
        print("WAIT", final.get("status"), final.get("analyzed"), final.get("remaining"))
        if final.get("status") in {"stopped", "complete", "error", "idle"}:
            break
        time.sleep(5)

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "batch_id": BATCH,
        "ui": ui,
        "before": before,
        "events": events,
        "observed_polls": observed,
        "final": final,
        "failures": [],
    }
    if not ui["has_continuous_button"]:
        report["failures"].append("continuous button missing")
    if busy.get("status") != "busy" and started.get("status") == "running":
        report["failures"].append("double-start did not return busy")
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("WROTE", OUT)
    print("FAILURES", report["failures"])


if __name__ == "__main__":
    main()
