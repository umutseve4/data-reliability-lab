from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from reliability_lab.pipeline import ingest_records, replay_quarantine
from reliability_lab.reporting import build_report, write_report


def event(event_id: str = "evt-1") -> dict:
    return {
        "event_id": event_id,
        "occurred_at": "2026-01-01T00:00:00Z",
        "source": "orders-api",
        "metric": "rows_processed",
        "value": 5,
    }


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "lab.db"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        return connection

    def test_accepts_valid_record(self) -> None:
        result = ingest_records([event()], self.db)
        self.assertEqual((result.accepted_rows, result.quarantined_rows), (1, 0))

    def test_is_idempotent_across_runs(self) -> None:
        ingest_records([event()], self.db)
        second = ingest_records([event()], self.db)
        self.assertEqual((second.accepted_rows, second.duplicate_rows), (0, 1))
        with self.connect() as db:
            count = db.execute("SELECT COUNT(*) FROM bronze_events").fetchone()[0]
            self.assertEqual(count, 1)

    def test_quarantines_contract_violation(self) -> None:
        result = ingest_records([{**event(), "value": -1}], self.db)
        self.assertEqual(result.quarantined_rows, 1)
        with self.connect() as db:
            row = db.execute("SELECT reason, status FROM quarantine_events").fetchone()
        self.assertIn("non-negative", row["reason"])
        self.assertEqual(row["status"], "pending")

    def test_failed_run_is_persisted(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "injected"):
            ingest_records([event("a"), event("b")], self.db, fail_after=1)
        with self.connect() as db:
            row = db.execute("SELECT status, error FROM pipeline_runs").fetchone()
        self.assertEqual(row["status"], "failed")
        self.assertIn("injected pipeline failure", row["error"])

    def test_lineage_is_recorded(self) -> None:
        result = ingest_records([event()], self.db)
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM lineage_edges WHERE run_id=?", (result.run_id,)
            ).fetchone()
        self.assertEqual(row["source_asset"], "jsonl:raw_events")
        self.assertEqual(row["target_asset"], "sqlite:bronze_events")
        self.assertEqual(row["row_count"], 1)

    def test_replay_keeps_invalid_payload_pending(self) -> None:
        ingest_records([{**event(), "value": -1}], self.db)
        result = replay_quarantine(self.db)
        self.assertEqual(result, {"attempted": 1, "replayed": 0, "still_invalid": 1})

    def test_replay_accepts_repaired_payload(self) -> None:
        ingest_records([{**event(), "value": -1}], self.db)
        with self.connect() as db:
            db.execute(
                "UPDATE quarantine_events SET payload=?",
                (json.dumps(event("repaired")),),
            )
            db.commit()
        result = replay_quarantine(self.db)
        self.assertEqual(result["replayed"], 1)
        with self.connect() as db:
            status = db.execute("SELECT status FROM quarantine_events").fetchone()[0]
            bronze = db.execute("SELECT COUNT(*) FROM bronze_events").fetchone()[0]
        self.assertEqual((status, bronze), ("replayed", 1))

    def test_report_fails_breached_quarantine_slo(self) -> None:
        ingest_records([event("ok"), {**event("bad"), "value": -1}], self.db)
        report = build_report(self.db, quarantine_slo=0.05)
        self.assertFalse(report["slo"]["met"])
        self.assertEqual(report["slo"]["actual"], 0.5)
        self.assertEqual(
            report["diagnostics"]["quarantine_reason_counts"],
            {"value must be non-negative": 1},
        )
        self.assertEqual(report["diagnostics"]["lineage"], {"edges": 1, "recorded_rows": 1})

    def test_report_file_is_reproducible_json(self) -> None:
        ingest_records([event()], self.db)
        output = Path(self.tmp.name) / "report.json"
        expected = write_report(self.db, output)
        self.assertEqual(json.loads(output.read_text()), expected)

    def test_recovery_after_failure_preserves_invariants(self) -> None:
        records = [event("evt-a"), event("evt-b"), {**event("evt-bad"), "value": -1}]
        with self.assertRaisesRegex(RuntimeError, "injected"):
            ingest_records(records, self.db, fail_after=1)
        recovered = ingest_records(records, self.db)
        self.assertEqual(
            (recovered.accepted_rows, recovered.duplicate_rows, recovered.quarantined_rows),
            (1, 1, 1),
        )

        with self.connect() as db:
            bronze_count = db.execute("SELECT COUNT(*) FROM bronze_events").fetchone()[0]
            quarantine_count = db.execute("SELECT COUNT(*) FROM quarantine_events").fetchone()[0]
            statuses = db.execute(
                "SELECT status, input_rows, accepted_rows, duplicate_rows, quarantined_rows "
                "FROM pipeline_runs ORDER BY started_at"
            ).fetchall()
            lineage = db.execute(
                "SELECT row_count FROM lineage_edges ORDER BY recorded_at"
            ).fetchall()

        self.assertEqual(bronze_count, 2)
        self.assertEqual(quarantine_count, 1)
        self.assertEqual(
            [tuple(row) for row in statuses],
            [("failed", 2, 1, 0, 0), ("success", 3, 1, 1, 1)],
        )
        self.assertEqual([row["row_count"] for row in lineage], [1])

    def test_replay_repaired_duplicate_is_idempotent(self) -> None:
        ingest_records([event("evt-1"), {**event("evt-bad"), "value": -1}], self.db)
        with self.connect() as db:
            db.execute(
                "UPDATE quarantine_events SET payload=?",
                (json.dumps(event("evt-1")),),
            )
            db.commit()
        replay = replay_quarantine(self.db)
        self.assertEqual(replay, {"attempted": 1, "replayed": 1, "still_invalid": 0})
        with self.connect() as db:
            bronze_count = db.execute("SELECT COUNT(*) FROM bronze_events").fetchone()[0]
            row = db.execute("SELECT status, replayed_event_id FROM quarantine_events").fetchone()
        self.assertEqual(bronze_count, 1)
        self.assertEqual((row["status"], row["replayed_event_id"]), ("replayed", "evt-1"))


if __name__ == "__main__":
    unittest.main()
