<h1 align="center">Data Reliability Lab</h1>

<p align="center">
  A pipeline that only works on clean input proves nothing.<br>
  This one is built to be <b>broken on purpose</b> — bad contracts, duplicate events,<br>
  a crash halfway through — and to leave evidence behind every time.
</p>

<p align="center">
  <a href="https://github.com/umutseve4/data-reliability-lab/actions/workflows/ci.yml"><img src="https://github.com/umutseve4/data-reliability-lab/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/tests-17-FF4D4F?style=flat-square" alt="17 tests">
  <img src="https://img.shields.io/badge/python-3.11%20%C2%B7%203.12%20%C2%B7%203.13-FF4D4F?style=flat-square" alt="Python 3.11, 3.12, 3.13">
</p>

---

## Run it in 60 seconds

```bash
python -m pip install -e . ruff
python -m unittest discover -s tests -v
reliability-lab run --source data/events.jsonl --db artifacts/lab.db
reliability-lab report --db artifacts/lab.db --output artifacts/report.json
```

The sample contains exactly `3` rows: `2` valid and `1` intentionally invalid.
The generated quarantine ratio is therefore `0.3333333333333333`, which
**intentionally breaches** the default `0.05` SLO. A green report on this input
would mean the lab is lying to you.

## Then break it on purpose

```bash
# Persist a failed run after processing one row.
reliability-lab run --source data/events.jsonl --db artifacts/fault.db --fail-after 1

# Retry pending quarantine rows after repairing their stored payloads.
reliability-lab replay --db artifacts/lab.db

# Re-run the same source; valid events are counted as duplicates, not reinserted.
reliability-lab run --source data/events.jsonl --db artifacts/lab.db
```

## The slice

```text
JSONL source
    |
    v
contract validation ----invalid----> quarantine_events ----repair/replay----+
    |                                                                        |
   valid                                                                     |
    v                                                                        v
bronze_events (event_id PK, INSERT OR IGNORE) <------------------------------+
    |
    +--> pipeline_runs + lineage_edges + reliability report
```

- strict event contract with UTC timestamp normalization;
- idempotent writes through an `event_id` primary key;
- quarantine with reason, payload and replay state;
- controlled runtime fault injection through `--fail-after`;
- persisted success **and failure** runs;
- source-to-target lineage evidence;
- JSON SLO report for quarantine ratio, failed runs and pending replay;
- 17 unit and integration tests;
- Python 3.11, 3.12 and 3.13 CI matrix;
- non-root container and hardened Compose defaults.

An SLO is a numeric reliability target; this lab uses a maximum quarantine ratio
of `0.05` by default.

## Every claim maps to a test

| Engineering claim | Executable evidence |
|---|---|
| Contract enforcement | `tests/test_contracts.py` |
| Idempotency | `test_is_idempotent_across_runs` |
| Quarantine and replay | `test_quarantines_contract_violation`, replay tests |
| Failure persistence | `test_failed_run_is_persisted` |
| Lineage | `test_lineage_is_recorded` |
| SLO calculation | report tests and CI artifact |
| Reproducibility | `Dockerfile`, `docker-compose.yml`, CI matrix and `container-smoke` job |

## Limits — read this first

- SQLite is deliberate for a deterministic zero-runtime-dependency slice; it does **not** prove distributed scale or high write concurrency.
- Replay currently expects a repaired payload to be written back before retry.
- Lineage is table-level rather than column-level.
- No orchestrator, alert transport, cloud object store or PostgreSQL adapter is implemented.
- Container base-image digest pinning and automated SBOM generation remain hardening tasks.

Status vocabulary used in this repository:

- **Implemented:** the vertical slice and its tests are present.
- **Locally tested:** all `17` tests and the end-to-end smoke run passed in the development environment.
- **Remotely verified:** only after the current `main` GitHub Actions run passes for lint, format, Python 3.11/3.12/3.13 tests, CLI smoke and container smoke.
- **Deployed:** not applicable; this is an executable lab, not a hosted service.
- **Production-ready:** no.

## Deterministic failure/recovery drill

```bash
rm -rf artifacts && mkdir -p artifacts
reliability-lab run --source data/events.jsonl --db artifacts/recovery.db --fail-after 1 || true
reliability-lab run --source data/events.jsonl --db artifacts/recovery.db
python - <<'PY'
import sqlite3
db = sqlite3.connect("artifacts/recovery.db")
print(db.execute("SELECT status,input_rows,accepted_rows,duplicate_rows,quarantined_rows FROM pipeline_runs ORDER BY started_at").fetchall())
print(db.execute("SELECT COUNT(*) FROM bronze_events").fetchone()[0])
print(db.execute("SELECT COUNT(*) FROM quarantine_events").fetchone()[0])
print(db.execute("SELECT row_count FROM lineage_edges ORDER BY recorded_at").fetchall())
PY
```

Expected deterministic invariants:

- run status tuples are exactly `[('failed', 2, 1, 0, 0), ('success', 3, 1, 1, 1)]`;
- `bronze_events` count is `2`;
- `quarantine_events` count is `1`;
- lineage `row_count` rows are exactly `[(1,)]`.

## Next acceptance gate

Add a PostgreSQL 16 adapter that passes the same behavior tests, then add
concurrent ingestion and crash-recovery tests. Do not add orchestration until
those reliability semantics remain green.

See [ADR-001](docs/adr/001-sqlite-vertical-slice.md), [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

---

MIT
