"""SQLite persistence with explicit bronze, quarantine, lineage and run tables."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS bronze_events (
    event_id TEXT PRIMARY KEY,
    occurred_at TEXT NOT NULL,
    source TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL NOT NULL,
    ingested_at TEXT NOT NULL,
    run_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quarantine_events (
    quarantine_id INTEGER PRIMARY KEY AUTOINCREMENT,
    payload TEXT NOT NULL,
    reason TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_attempt_at TEXT,
    status TEXT NOT NULL CHECK(status IN ('pending', 'replayed')) DEFAULT 'pending',
    replayed_event_id TEXT
);
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL CHECK(status IN ('running', 'success', 'failed')),
    input_rows INTEGER NOT NULL DEFAULT 0,
    accepted_rows INTEGER NOT NULL DEFAULT 0,
    duplicate_rows INTEGER NOT NULL DEFAULT 0,
    quarantined_rows INTEGER NOT NULL DEFAULT 0,
    error TEXT
);
CREATE TABLE IF NOT EXISTS lineage_edges (
    run_id TEXT NOT NULL,
    source_asset TEXT NOT NULL,
    target_asset TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    recorded_at TEXT NOT NULL,
    PRIMARY KEY (run_id, source_asset, target_asset)
);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    return connection
