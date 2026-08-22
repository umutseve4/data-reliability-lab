# ADR-001: Use SQLite for the first reliability vertical slice

- Status: Accepted
- Date: 2026-08-22

## Context

The portfolio already contains broad data platforms. This repository must prove reliability behavior rather than repeat infrastructure breadth. A database service would increase setup cost before the contract, idempotency, quarantine, replay, lineage and SLO semantics are verified.

## Decision

Use Python's standard-library `sqlite3` module behind a small persistence boundary. Keep the schema explicit and test all reliability behavior against real transactions.

## Consequences

Positive:
- zero runtime dependencies;
- deterministic local and CI execution;
- fast fault-injection tests;
- SQL artifacts remain inspectable.

Negative:
- no claim of distributed scale or high write concurrency;
- a PostgreSQL adapter and integration test remain required before production-readiness claims.
