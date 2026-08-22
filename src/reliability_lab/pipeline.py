"""Idempotent ingestion, quarantine and replay pipeline."""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from .contracts import ContractViolation, validate_event
from .store import connect


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class RunResult:
    run_id: str
    status: str
    input_rows: int
    accepted_rows: int
    duplicate_rows: int
    quarantined_rows: int

    def as_dict(self) -> dict[str, str | int]:
        return asdict(self)


def _insert_event(db: sqlite3.Connection, event: dict, run_id: str) -> bool:
    cursor = db.execute(
        """INSERT OR IGNORE INTO bronze_events
        (event_id, occurred_at, source, metric, value, ingested_at, run_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            event["event_id"],
            event["occurred_at"],
            event["source"],
            event["metric"],
            event["value"],
            utc_now(),
            run_id,
        ),
    )
    return cursor.rowcount == 1


def ingest_records(
    records: Iterable[dict], db_path: str | Path, *, fail_after: int | None = None
) -> RunResult:
    """Ingest records atomically per row and preserve the run result on failure."""
    run_id = str(uuid.uuid4())
    started = utc_now()
    db = connect(db_path)
    db.execute(
        "INSERT INTO pipeline_runs(run_id, started_at, status) VALUES (?, ?, 'running')",
        (run_id, started),
    )
    db.commit()
    counts = {"input": 0, "accepted": 0, "duplicate": 0, "quarantined": 0}
    try:
        for raw in records:
            counts["input"] += 1
            if fail_after is not None and counts["input"] > fail_after:
                raise RuntimeError("injected pipeline failure")
            try:
                event = validate_event(raw)
            except ContractViolation as exc:
                db.execute(
                    """INSERT INTO quarantine_events(payload, reason, first_seen_at)
                    VALUES (?, ?, ?)""",
                    (json.dumps(raw, sort_keys=True), str(exc), utc_now()),
                )
                counts["quarantined"] += 1
            else:
                if _insert_event(db, event, run_id):
                    counts["accepted"] += 1
                else:
                    counts["duplicate"] += 1
            db.commit()
        db.execute(
            """INSERT INTO lineage_edges
            (run_id, source_asset, target_asset, row_count, recorded_at)
            VALUES (?, 'jsonl:raw_events', 'sqlite:bronze_events', ?, ?)""",
            (run_id, counts["accepted"], utc_now()),
        )
        db.execute(
            """UPDATE pipeline_runs SET finished_at=?, status='success', input_rows=?,
            accepted_rows=?, duplicate_rows=?, quarantined_rows=? WHERE run_id=?""",
            (
                utc_now(),
                counts["input"],
                counts["accepted"],
                counts["duplicate"],
                counts["quarantined"],
                run_id,
            ),
        )
        db.commit()
        return RunResult(
            run_id,
            "success",
            counts["input"],
            counts["accepted"],
            counts["duplicate"],
            counts["quarantined"],
        )
    except Exception as exc:
        db.execute(
            """UPDATE pipeline_runs SET finished_at=?, status='failed', input_rows=?,
            accepted_rows=?, duplicate_rows=?, quarantined_rows=?, error=? WHERE run_id=?""",
            (
                utc_now(),
                counts["input"],
                counts["accepted"],
                counts["duplicate"],
                counts["quarantined"],
                str(exc),
                run_id,
            ),
        )
        db.commit()
        raise
    finally:
        db.close()


def ingest_jsonl(
    source: str | Path,
    db_path: str | Path,
    *,
    fail_after: int | None = None,
) -> RunResult:
    with Path(source).open(encoding="utf-8") as handle:
        records = [json.loads(line) for line in handle if line.strip()]
    return ingest_records(records, db_path, fail_after=fail_after)


def replay_quarantine(db_path: str | Path) -> dict[str, int]:
    """Retry pending quarantine rows; valid repaired payloads become bronze rows."""
    db = connect(db_path)
    run_id = str(uuid.uuid4())
    replayed = still_invalid = 0
    rows = db.execute(
        "SELECT quarantine_id, payload FROM quarantine_events "
        "WHERE status='pending' ORDER BY quarantine_id"
    ).fetchall()
    for row in rows:
        attempted_at = utc_now()
        try:
            event = validate_event(json.loads(row["payload"]))
        except (ContractViolation, json.JSONDecodeError):
            still_invalid += 1
            db.execute(
                "UPDATE quarantine_events SET last_attempt_at=? WHERE quarantine_id=?",
                (attempted_at, row["quarantine_id"]),
            )
        else:
            _insert_event(db, event, run_id)
            replayed += 1
            db.execute(
                """UPDATE quarantine_events SET status='replayed', last_attempt_at=?,
                replayed_event_id=? WHERE quarantine_id=?""",
                (attempted_at, event["event_id"], row["quarantine_id"]),
            )
        db.commit()
    db.close()
    return {"attempted": len(rows), "replayed": replayed, "still_invalid": still_invalid}
