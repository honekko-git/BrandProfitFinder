"""FastAPI application entry point for the browser dashboard."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routes import router
from app.store import (
    BatchProfitResultStore,
    DashboardResultStore,
    InMemoryDashboardSnapshotStore,
    SQLiteMarketListingStore,
    SQLiteOpportunityStore,
    ValidationResultStore,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = PROJECT_ROOT / "static"


def create_app(
    *,
    result_store: DashboardResultStore | InMemoryDashboardSnapshotStore | None = None,
    validation_store: ValidationResultStore | None = None,
    opportunity_store: SQLiteOpportunityStore | None = None,
    market_listing_store: SQLiteMarketListingStore | None = None,
    database_path: Path | str | None = None,
) -> FastAPI:
    """Create the browser dashboard FastAPI application."""
    application = FastAPI(title="LuxuryBrandProfitFinder", version="1.0.0")
    application.state.result_store = result_store or DashboardResultStore()
    application.state.validation_store = validation_store or ValidationResultStore()
    application.state.opportunity_store = opportunity_store or SQLiteOpportunityStore(
        database_path=database_path,
    )
    application.state.market_listing_store = market_listing_store or SQLiteMarketListingStore(
        database_path=database_path,
    )
    application.state.batch_profit_store = BatchProfitResultStore()
    _install_browser_capture_cors(application)
    application.include_router(router)
    # Guard: sourcing detail must remain reachable after workspace UI ships.
    _assert_sourcing_detail_route_registered(application)
    if STATIC_DIR.exists():
        application.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    return application


def _install_browser_capture_cors(application: FastAPI) -> None:
    """Allow only extension capture/bulk endpoints to answer chrome-extension origins."""
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request as StarletteRequest
    from starlette.responses import Response

    allowed_prefixes = (
        "/acquisition-workspace/import/browser-capture",
        "/acquisition-workspace/bulk-acquisition/",
    )

    class BrowserCaptureCorsMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: StarletteRequest, call_next):
            path = request.url.path
            if not any(path.startswith(prefix) for prefix in allowed_prefixes):
                return await call_next(request)
            origin = request.headers.get("origin", "")
            allowed = origin.startswith("chrome-extension://") or origin in {"", "null"}
            if request.method == "OPTIONS":
                if not allowed:
                    return Response(status_code=403)
                response = Response(status_code=204)
            else:
                response = await call_next(request)
            if allowed:
                response.headers["Access-Control-Allow-Origin"] = origin or "*"
                response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
                response.headers["Access-Control-Allow-Headers"] = (
                    "Content-Type, Accept, X-BrandProfitFinder-Capture"
                )
                response.headers["Access-Control-Max-Age"] = "600"
                response.headers["Vary"] = "Origin"
            return response

    application.add_middleware(BrowserCaptureCorsMiddleware)


def _assert_sourcing_detail_route_registered(application: FastAPI) -> None:
    """Fail fast if the Product Detail route was not included."""
    expected = "/acquisition-workspace/candidate/{candidate_id}"
    paths: set[str] = set()
    for route in application.routes:
        path = getattr(route, "path", None)
        if isinstance(path, str):
            paths.add(path)
        included = getattr(route, "routes", None) or getattr(getattr(route, "app", None), "routes", None)
        if included:
            for child in included:
                child_path = getattr(child, "path", None)
                if isinstance(child_path, str):
                    paths.add(child_path)
        # FastAPI >=0.141 wraps include_router as _IncludedRouter
        original = getattr(route, "original_router", None)
        if original is not None:
            for child in getattr(original, "routes", []):
                child_path = getattr(child, "path", None)
                if isinstance(child_path, str):
                    paths.add(child_path)
    if expected not in paths:
        raise RuntimeError(
            f"Missing required route {expected!r}. "
            "Restart the web server so acquisition candidate detail is registered."
        )


app = create_app()


def run_web_server(*, host: str = "127.0.0.1", port: int = 8000) -> None:
    """Start the dashboard web server with uvicorn."""
    import os

    import uvicorn

    # Continuous profit analysis keeps an in-process worker thread. Auto-reload
    # would kill that thread mid-batch, so keep reload off unless explicitly enabled.
    reload_enabled = os.environ.get("BPF_WEB_RELOAD", "").strip().lower() in {"1", "true", "yes"}
    uvicorn.run("app.main:app", host=host, port=port, reload=reload_enabled)


if __name__ == "__main__":
    run_web_server()
