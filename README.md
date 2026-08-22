# Data Reliability Lab

[![CI](https://github.com/umutseve4/data-reliability-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/umutseve4/data-reliability-lab/actions/workflows/ci.yml)

A small, executable failure-simulation lab for data engineers. It demonstrates how a pipeline behaves when data violates a contract, events arrive more than once, or execution fails halfway through.

## Why this repository exists

A pipeline that only works on clean input proves little. Hiring-relevant reliability evidence is the ability to detect bad data, preserve evidence, avoid duplicate writes, replay safely and expose measurable service-level objectives (SLOs). An SLO is a numeric reliability target; this lab uses a maximum quarantine ratio of `0.05` by default.

## Implemented vertical slice

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
- persisted success and failure runs;
- source-to-target lineage evidence;
- JSON SLO report for quarantine ratio, failed runs and pending replay;
- 15 unit and integration tests;
- Python 3.11, 3.12 and 3.13 CI matrix;
- non-root container and hardened Compose defaults.

## Quick start

```bash
python -m pip install -e . ruff
ruff check .
ruff format --check .
python -m unittest discover -s tests -v
reliability-lab run --source data/events.jsonl --db artifacts/lab.db
reliability-lab report --db artifacts/lab.db --output artifacts/report.json
```

The sample contains exactly `3` rows: `2` valid and `1` intentionally invalid. Therefore the generated quarantine ratio is `0.3333333333333333`, which intentionally breaches the default `0.05` SLO.

## Failure experiments

```bash
# Persist a failed run after processing one row.
reliability-lab run --source data/events.jsonl --db artifacts/fault.db --fail-after 1

# Retry pending quarantine rows after repairing their stored payloads.
reliability-lab replay --db artifacts/lab.db

# Re-run the same source; valid events are counted as duplicates, not reinserted.
reliability-lab run --source data/events.jsonl --db artifacts/lab.db
```

## Evidence map

| Engineering claim | Executable evidence |
|---|---|
| Contract enforcement | `tests/test_contracts.py` |
| Idempotency | `test_is_idempotent_across_runs` |
| Quarantine and replay | `test_quarantines_contract_violation`, replay tests |
| Failure persistence | `test_failed_run_is_persisted` |
| Lineage | `test_lineage_is_recorded` |
| SLO calculation | report tests and CI artifact |
| Reproducibility | `Dockerfile`, `docker-compose.yml`, CI matrix and `container-smoke` job |

## Status vocabulary

- **Implemented:** the vertical slice and its tests are present.
- **Locally tested:** all `15` tests and the end-to-end smoke run passed in the development environment.
- **Remotely verified:** only after the current `main` GitHub Actions run passes for lint, format, Python 3.11/3.12/3.13 tests, CLI smoke and container smoke.
- **Deployed:** not applicable; this is an executable lab, not a hosted service.
- **Production-ready:** no.

## Known limitations

- SQLite is deliberate for a deterministic zero-runtime-dependency slice; it does not prove distributed scale or high write concurrency.
- Replay currently expects a repaired payload to be written back before retry.
- Lineage is table-level rather than column-level.
- No orchestrator, alert transport, cloud object store or PostgreSQL adapter is implemented.
- Container base-image digest pinning and automated SBOM generation remain hardening tasks.

## Next acceptance gate

Add a PostgreSQL 16 adapter that passes the same behavior tests, then add concurrent ingestion and crash-recovery tests. Do not add orchestration until those reliability semantics remain green.

See [ADR-001](docs/adr/001-sqlite-vertical-slice.md), [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

## License

MIT
