"""Lightweight continuous profit-analysis orchestration for the acquisition workspace.

Repeatedly invokes the existing ``AcquisitionWorkspaceService.run_batch_profit``
tranche workflow. Does not duplicate matching, ranking, or ProfitCalculator logic.
"""

from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from marketplace.acquisition_workspace.profit_bridge import MAX_BATCH_CANDIDATES


RunBatchCallable = Callable[..., Any]


@dataclass
class ContinuousAnalysisProgress:
    workspace_batch_id: str
    status: str = "idle"  # idle|running|stopping|stopped|complete|error|busy
    total_candidates: int = 0
    eligible: int = 0
    analyzed: int = 0
    remaining: int = 0
    failed: int = 0
    currently_running: bool = False
    completion_percent: float = 0.0
    estimated_remaining_batches: int = 0
    status_message: str = ""
    detail_message: str = ""
    last_completed_count: int = 0
    error_message: str = ""
    stop_requested: bool = False
    batches_completed: int = 0
    user_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class _Session:
    workspace_batch_id: str
    stop_event: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None
    progress: ContinuousAnalysisProgress = field(default_factory=lambda: ContinuousAnalysisProgress(""))
    lock: threading.Lock = field(default_factory=threading.Lock)


class ContinuousAnalysisController:
    """One continuous-analysis session per workspace batch (process-local)."""

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._sessions: dict[str, _Session] = {}

    def get_progress(self, workspace_batch_id: str, service) -> ContinuousAnalysisProgress:
        stats = self._workspace_stats(service, workspace_batch_id)
        with self._guard:
            session = self._sessions.get(workspace_batch_id)
        if session is None:
            progress = ContinuousAnalysisProgress(workspace_batch_id=workspace_batch_id, status="idle")
            self._apply_stats(progress, stats)
            if stats["remaining"] == 0 and stats["eligible"] > 0:
                progress.status = "complete"
                progress.user_message = "すべて分析済みです。"
                progress.status_message = "すべて分析済みです。"
            return progress
        with session.lock:
            progress = ContinuousAnalysisProgress(**asdict(session.progress))
        self._apply_stats(progress, stats)
        # Keep session status authoritative while active.
        if progress.status in {"running", "stopping"}:
            progress.currently_running = True
        return progress

    def start(
        self,
        workspace_batch_id: str,
        service,
        *,
        cost_profile_name: str = "standard",
        use_cache: bool = True,
        run_batch: RunBatchCallable | None = None,
        html_by_query: dict[str, str] | None = None,
        mercari_html_by_query: dict[str, str] | None = None,
        open_html_by_query: dict[str, str] | None = None,
        sleep_between_batches: float = 0.0,
    ) -> ContinuousAnalysisProgress:
        stats = self._workspace_stats(service, workspace_batch_id)
        if stats["remaining"] == 0 and stats["eligible"] > 0:
            progress = ContinuousAnalysisProgress(
                workspace_batch_id=workspace_batch_id,
                status="complete",
                user_message="すべて分析済みです。",
                status_message="すべて分析済みです。",
            )
            self._apply_stats(progress, stats)
            return progress
        if stats["eligible"] == 0:
            progress = ContinuousAnalysisProgress(
                workspace_batch_id=workspace_batch_id,
                status="complete",
                user_message="すべて分析済みです。",
                status_message="対象となる候補がありません。",
            )
            self._apply_stats(progress, stats)
            return progress

        with self._guard:
            existing = self._sessions.get(workspace_batch_id)
            if existing is not None and existing.thread is not None and existing.thread.is_alive():
                with existing.lock:
                    busy = ContinuousAnalysisProgress(**asdict(existing.progress))
                busy.status = "busy"
                busy.user_message = "現在このワークスペースでは分析が実行中です。"
                busy.status_message = busy.user_message
                busy.currently_running = True
                self._apply_stats(busy, stats)
                return busy

            session = _Session(workspace_batch_id=workspace_batch_id)
            session.progress = ContinuousAnalysisProgress(
                workspace_batch_id=workspace_batch_id,
                status="running",
                currently_running=True,
                status_message="連続分析中...",
                detail_message="Yahoo!オークション検索中...",
                user_message="連続分析中...",
            )
            self._apply_stats(session.progress, stats)
            self._sessions[workspace_batch_id] = session

            runner = run_batch or service.run_batch_profit

            def _worker() -> None:
                self._run_loop(
                    session=session,
                    service=service,
                    runner=runner,
                    cost_profile_name=cost_profile_name,
                    use_cache=use_cache,
                    html_by_query=html_by_query,
                    mercari_html_by_query=mercari_html_by_query,
                    open_html_by_query=open_html_by_query,
                    sleep_between_batches=sleep_between_batches,
                )

            session.thread = threading.Thread(
                target=_worker,
                name=f"continuous-profit-{workspace_batch_id}",
                daemon=True,
            )
            session.thread.start()

        return self.get_progress(workspace_batch_id, service)

    def stop(self, workspace_batch_id: str, service) -> ContinuousAnalysisProgress:
        with self._guard:
            session = self._sessions.get(workspace_batch_id)
        if session is None:
            progress = self.get_progress(workspace_batch_id, service)
            progress.user_message = "連続分析は実行されていません。"
            return progress
        session.stop_event.set()
        with session.lock:
            if session.progress.status == "running":
                session.progress.status = "stopping"
                session.progress.stop_requested = True
                session.progress.status_message = "停止要求を受け付けました。現在の20件が完了するまで待ちます…"
                session.progress.detail_message = session.progress.status_message
                session.progress.user_message = session.progress.status_message
        return self.get_progress(workspace_batch_id, service)

    def _run_loop(
        self,
        *,
        session: _Session,
        service,
        runner: RunBatchCallable,
        cost_profile_name: str,
        use_cache: bool,
        html_by_query: dict[str, str] | None,
        mercari_html_by_query: dict[str, str] | None,
        open_html_by_query: dict[str, str] | None,
        sleep_between_batches: float,
    ) -> None:
        batch_id = session.workspace_batch_id
        try:
            while True:
                if session.stop_event.is_set():
                    self._mark_stopped(session, service)
                    return

                stats = self._workspace_stats(service, batch_id)
                with session.lock:
                    self._apply_stats(session.progress, stats)
                    session.progress.currently_running = True
                    session.progress.status = "running"
                    session.progress.status_message = "連続分析中..."
                    session.progress.detail_message = "Yahoo!オークション検索中..."
                    session.progress.user_message = "連続分析中..."

                if stats["remaining"] <= 0:
                    with session.lock:
                        session.progress.status = "complete"
                        session.progress.currently_running = False
                        session.progress.status_message = "すべて分析済みです。"
                        session.progress.detail_message = ""
                        session.progress.user_message = "すべて分析済みです。"
                        self._apply_stats(session.progress, stats)
                    return

                phase_stop = threading.Event()
                ticker = threading.Thread(
                    target=self._phase_ticker,
                    args=(session, phase_stop),
                    daemon=True,
                )
                ticker.start()
                try:
                    run = runner(
                        batch_id,
                        cost_profile_name=cost_profile_name,
                        use_cache=use_cache,
                        html_by_query=html_by_query,
                        mercari_html_by_query=mercari_html_by_query,
                        open_html_by_query=open_html_by_query,
                    )
                finally:
                    phase_stop.set()
                    ticker.join(timeout=1.0)

                status = getattr(getattr(run, "summary", None), "status", "") or ""
                stats_after = self._workspace_stats(service, batch_id)
                with session.lock:
                    session.progress.batches_completed += 0 if status == "already_complete" else 1
                    session.progress.last_completed_count = stats_after["analyzed"]
                    self._apply_stats(session.progress, stats_after)
                    session.progress.detail_message = "利益計算中..."

                if status == "already_complete" or stats_after["remaining"] <= 0:
                    with session.lock:
                        session.progress.status = "complete"
                        session.progress.currently_running = False
                        session.progress.status_message = "すべて分析済みです。"
                        session.progress.detail_message = ""
                        session.progress.user_message = "すべて分析済みです。"
                    return

                if session.stop_event.is_set():
                    self._mark_stopped(session, service)
                    return

                if sleep_between_batches > 0:
                    time.sleep(sleep_between_batches)
        except Exception as exc:  # noqa: BLE001 — surface to UI, stop loop
            stats = self._workspace_stats(service, batch_id)
            with session.lock:
                session.progress.status = "error"
                session.progress.currently_running = False
                session.progress.error_message = str(exc)
                session.progress.status_message = "分析中にエラーが発生しました。"
                session.progress.detail_message = ""
                session.progress.user_message = "分析中にエラーが発生しました。"
                session.progress.last_completed_count = stats["analyzed"]
                self._apply_stats(session.progress, stats)

    def _mark_stopped(self, session: _Session, service) -> None:
        stats = self._workspace_stats(service, session.workspace_batch_id)
        with session.lock:
            session.progress.status = "stopped"
            session.progress.currently_running = False
            session.progress.stop_requested = True
            self._apply_stats(session.progress, stats)
            analyzed = session.progress.analyzed
            remaining = session.progress.remaining
            eligible = session.progress.eligible
            session.progress.last_completed_count = analyzed
            session.progress.status_message = f"{analyzed} / {eligible} 完了"
            session.progress.detail_message = f"残り{remaining}件"
            session.progress.user_message = (
                f"{analyzed} / {eligible} 完了\n残り{remaining}件"
            )

    @staticmethod
    def _phase_ticker(session: _Session, stop_event: threading.Event) -> None:
        phases = (
            "Yahoo!オークション検索中...",
            "Mercari検索中...",
            "利益計算中...",
        )
        index = 0
        while not stop_event.wait(2.0):
            with session.lock:
                if session.progress.status not in {"running", "stopping"}:
                    return
                session.progress.detail_message = phases[index % len(phases)]
            index += 1

    @staticmethod
    def _workspace_stats(service, workspace_batch_id: str) -> dict[str, int]:
        _, rows = service.get_batch(workspace_batch_id)
        total = len(rows)
        eligible_rows = [
            item
            for item in rows
            if item.eligible_for_profit_check
            and not item.duplicate_of
            and item.quality_grade != "REJECTED"
        ]
        eligible = len(eligible_rows)

        from marketplace.acquisition_workspace.analysis_version import is_profit_analysis_current

        analyzed = sum(1 for item in eligible_rows if is_profit_analysis_current(item))
        remaining = eligible - analyzed
        failed = 0
        return {
            "total_candidates": total,
            "eligible": eligible,
            "analyzed": analyzed,
            "remaining": max(0, remaining),
            "failed": failed,
        }

    @staticmethod
    def _apply_stats(progress: ContinuousAnalysisProgress, stats: dict[str, int]) -> None:
        progress.total_candidates = stats["total_candidates"]
        progress.eligible = stats["eligible"]
        progress.analyzed = stats["analyzed"]
        progress.remaining = stats["remaining"]
        progress.failed = stats["failed"]
        if stats["eligible"] > 0:
            progress.completion_percent = round(100.0 * stats["analyzed"] / stats["eligible"], 1)
        else:
            progress.completion_percent = 100.0 if stats["total_candidates"] else 0.0
        progress.estimated_remaining_batches = (
            (stats["remaining"] + MAX_BATCH_CANDIDATES - 1) // MAX_BATCH_CANDIDATES
            if stats["remaining"] > 0
            else 0
        )


_CONTROLLER: ContinuousAnalysisController | None = None
_CONTROLLER_LOCK = threading.Lock()


def get_continuous_analysis_controller() -> ContinuousAnalysisController:
    global _CONTROLLER
    with _CONTROLLER_LOCK:
        if _CONTROLLER is None:
            _CONTROLLER = ContinuousAnalysisController()
        return _CONTROLLER


def reset_continuous_analysis_controller_for_tests() -> ContinuousAnalysisController:
    """Replace the process-local singleton (tests only)."""
    global _CONTROLLER
    with _CONTROLLER_LOCK:
        _CONTROLLER = ContinuousAnalysisController()
        return _CONTROLLER
