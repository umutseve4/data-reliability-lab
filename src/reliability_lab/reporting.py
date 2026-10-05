"""Reliability SLO computation and incident report generation."""

from __future__ import annotations

import json
from pathlib import Path

from .store import connect


def build_report(db_path: str | Path, *, quarantine_slo: float = 0.05) -> dict:
    db = connect(db_path)
    totals = db.execute(
        """SELECT COALESCE(SUM(input_rows), 0) input_rows,
        COALESCE(SUM(quarantined_rows), 0) quarantined_rows,
        SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) failed_runs,
        COUNT(*) total_runs FROM pipeline_runs"""
    ).fetchone()
    pending = db.execute(
        "SELECT COUNT(*) AS count FROM quarantine_events WHERE status='pending'"
    ).fetchone()["count"]
    quarantine_reasons = {
        row["reason"]: row["count"]
        for row in db.execute(
            """SELECT reason, COUNT(*) AS count FROM quarantine_events
            GROUP BY reason ORDER BY count DESC, reason ASC"""
        ).fetchall()
    }
    lineage_totals = db.execute(
        "SELECT COUNT(*) AS edges, COALESCE(SUM(row_count), 0) AS rows FROM lineage_edges"
    ).fetchone()
    input_rows = totals["input_rows"]
    ratio = totals["quarantined_rows"] / input_rows if input_rows else 0.0
    report = {
        "slo": {
            "name": "quarantine_ratio",
            "target_max": quarantine_slo,
            "actual": ratio,
            "met": ratio <= quarantine_slo,
        },
        "runs": {"total": totals["total_runs"], "failed": totals["failed_runs"]},
        "rows": {
            "input": input_rows,
            "quarantined": totals["quarantined_rows"],
            "pending_replay": pending,
        },
        "diagnostics": {
            "quarantine_reason_counts": quarantine_reasons,
            "lineage": {
                "edges": lineage_totals["edges"],
                "recorded_rows": lineage_totals["rows"],
            },
        },
    }
    db.close()
    return report


def write_report(
    db_path: str | Path,
    output: str | Path,
    *,
    quarantine_slo: float = 0.05,
) -> dict:
    report = build_report(db_path, quarantine_slo=quarantine_slo)
    Path(output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
