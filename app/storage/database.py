"""SQLite database helpers for opportunity storage."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DEFAULT_DATABASE_PATH = Path("data/brand_profit.db")

CREATE_OPPORTUNITIES_TABLE = """
CREATE TABLE IF NOT EXISTS opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT NOT NULL,
    brand TEXT NOT NULL,
    category TEXT NOT NULL,
    purchase_source TEXT NOT NULL,
    purchase_url TEXT NOT NULL,
    purchase_price REAL NOT NULL,
    selling_market TEXT NOT NULL,
    selling_url TEXT NOT NULL,
    selling_price REAL NOT NULL,
    estimated_profit REAL NOT NULL,
    profit_margin REAL NOT NULL,
    demand_score REAL NOT NULL,
    turnover_score REAL NOT NULL,
    arbitrage_score REAL NOT NULL,
    decision TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

CREATE_MARKET_LISTINGS_TABLE = """
CREATE TABLE IF NOT EXISTS market_listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    brand TEXT NOT NULL,
    category TEXT NOT NULL,
    condition TEXT NOT NULL,
    price REAL NOT NULL,
    currency TEXT NOT NULL,
    market_name TEXT NOT NULL,
    url TEXT NOT NULL,
    external_key TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""

CREATE_LIVE_ACQUISITION_EVIDENCE_TABLE = """
CREATE TABLE IF NOT EXISTS live_acquisition_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    search_query TEXT NOT NULL,
    listing_url TEXT NOT NULL,
    displayed_price REAL NOT NULL,
    currency TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    acquisition_status TEXT NOT NULL,
    matching_summary TEXT NOT NULL,
    profit_result TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""

CREATE_YAHOO_SEARCH_CACHE_TABLE = """
CREATE TABLE IF NOT EXISTS yahoo_search_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    normalized_query TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    acquisition_status TEXT NOT NULL,
    raw_sample_count INTEGER NOT NULL,
    samples_json TEXT NOT NULL,
    diagnostics_json TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""

CREATE_BATCH_RUNS_TABLE = """
CREATE TABLE IF NOT EXISTS batch_runs (
    batch_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    cost_profile TEXT NOT NULL,
    exchange_rate TEXT NOT NULL,
    total_candidates INTEGER NOT NULL,
    processed_count INTEGER NOT NULL,
    strong_candidate_count INTEGER NOT NULL,
    review_count INTEGER NOT NULL,
    hold_count INTEGER NOT NULL,
    reject_count INTEGER NOT NULL,
    failed_count INTEGER NOT NULL,
    blocked_count INTEGER NOT NULL,
    total_yahoo_requests INTEGER NOT NULL,
    cache_hits INTEGER NOT NULL,
    status TEXT NOT NULL,
    summary_json TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""

CREATE_BATCH_PROFIT_RESULTS_TABLE = """
CREATE TABLE IF NOT EXISTS batch_profit_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    rank INTEGER NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""

CREATE_COMPARABLE_EVIDENCE_TABLE = """
CREATE TABLE IF NOT EXISTS comparable_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    yahoo_title TEXT NOT NULL,
    price_jpy INTEGER NOT NULL,
    url TEXT NOT NULL,
    matching_score INTEGER NOT NULL,
    accepted INTEGER NOT NULL,
    rejection_reasons TEXT NOT NULL,
    subtype TEXT NOT NULL,
    material TEXT NOT NULL,
    condition_label TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""

CREATE_ACQUISITION_WORKSPACE_BATCHES_TABLE = """
CREATE TABLE IF NOT EXISTS acquisition_workspace_batches (
    workspace_batch_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    total_rows INTEGER NOT NULL,
    accepted_count INTEGER NOT NULL,
    warning_count INTEGER NOT NULL,
    rejected_count INTEGER NOT NULL,
    duplicate_count INTEGER NOT NULL,
    selected_count INTEGER NOT NULL,
    status TEXT NOT NULL
)
"""

CREATE_ACQUISITION_CANDIDATES_TABLE = """
CREATE TABLE IF NOT EXISTS acquisition_candidates (
    candidate_id TEXT PRIMARY KEY,
    workspace_batch_id TEXT NOT NULL,
    candidate_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

CREATE_ACQUISITION_IMPORT_EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS acquisition_import_events (
    event_id TEXT PRIMARY KEY,
    workspace_batch_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    parser_strategy TEXT NOT NULL,
    source_filename TEXT NOT NULL,
    source_file_hash TEXT NOT NULL,
    diagnostics_json TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""


def resolve_database_path(path: Path | str | None = None) -> Path:
    """Resolve the SQLite database path from override or environment."""
    if path is not None:
        return Path(path)
    env_path = os.getenv("BRAND_PROFIT_DB_PATH")
    if env_path:
        return Path(env_path)
    return DEFAULT_DATABASE_PATH


def connect(database_path: Path | str | None = None) -> sqlite3.Connection:
    """Open one SQLite connection and ensure schema exists."""
    db_path = resolve_database_path(database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    initialize_schema(connection)
    return connection


def initialize_schema(connection: sqlite3.Connection) -> None:
    """Create opportunity tables when missing."""
    connection.execute(CREATE_OPPORTUNITIES_TABLE)
    connection.execute(CREATE_MARKET_LISTINGS_TABLE)
    connection.execute(CREATE_LIVE_ACQUISITION_EVIDENCE_TABLE)
    connection.execute(CREATE_YAHOO_SEARCH_CACHE_TABLE)
    connection.execute(CREATE_BATCH_RUNS_TABLE)
    connection.execute(CREATE_BATCH_PROFIT_RESULTS_TABLE)
    connection.execute(CREATE_COMPARABLE_EVIDENCE_TABLE)
    connection.execute(CREATE_ACQUISITION_WORKSPACE_BATCHES_TABLE)
    connection.execute(CREATE_ACQUISITION_CANDIDATES_TABLE)
    connection.execute(CREATE_ACQUISITION_IMPORT_EVENTS_TABLE)
    connection.commit()

