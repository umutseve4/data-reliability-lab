"""Data contract validation for incoming telemetry events."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

REQUIRED_FIELDS = {"event_id", "occurred_at", "source", "metric", "value"}
ALLOWED_METRICS = {"latency_ms", "rows_processed", "error_count"}


class ContractViolation(ValueError):
    """Raised when an event violates the declared data contract."""


def validate_event(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize one event without mutating the input."""
    missing = REQUIRED_FIELDS - raw.keys()
    if missing:
        raise ContractViolation(f"missing fields: {', '.join(sorted(missing))}")

    event_id = raw["event_id"]
    if not isinstance(event_id, str) or not event_id.strip():
        raise ContractViolation("event_id must be a non-empty string")

    source = raw["source"]
    if not isinstance(source, str) or not source.strip():
        raise ContractViolation("source must be a non-empty string")

    metric = raw["metric"]
    if metric not in ALLOWED_METRICS:
        raise ContractViolation(f"unsupported metric: {metric!r}")

    value = raw["value"]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ContractViolation("value must be numeric")
    if value < 0:
        raise ContractViolation("value must be non-negative")

    occurred_at = raw["occurred_at"]
    if not isinstance(occurred_at, str):
        raise ContractViolation("occurred_at must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractViolation("occurred_at must be valid ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ContractViolation("occurred_at must include a timezone")
    parsed = parsed.astimezone(UTC)

    return {
        "event_id": event_id.strip(),
        "occurred_at": parsed.isoformat().replace("+00:00", "Z"),
        "source": source.strip(),
        "metric": metric,
        "value": float(value),
    }
