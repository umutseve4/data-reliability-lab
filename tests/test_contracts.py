from __future__ import annotations

import unittest

from reliability_lab.contracts import ContractViolation, validate_event

VALID = {
    "event_id": "evt-1",
    "occurred_at": "2026-01-01T00:00:00Z",
    "source": "orders-api",
    "metric": "latency_ms",
    "value": 12,
}


class ContractTests(unittest.TestCase):
    def test_normalizes_valid_event(self) -> None:
        event = validate_event(VALID)
        self.assertEqual(event["value"], 12.0)
        self.assertEqual(event["occurred_at"], "2026-01-01T00:00:00Z")

    def test_rejects_missing_field(self) -> None:
        bad = {key: value for key, value in VALID.items() if key != "source"}
        with self.assertRaisesRegex(ContractViolation, "missing fields: source"):
            validate_event(bad)

    def test_rejects_unknown_metric(self) -> None:
        with self.assertRaisesRegex(ContractViolation, "unsupported metric"):
            validate_event({**VALID, "metric": "cpu"})

    def test_rejects_negative_value(self) -> None:
        with self.assertRaisesRegex(ContractViolation, "non-negative"):
            validate_event({**VALID, "value": -1})

    def test_rejects_boolean_as_number(self) -> None:
        with self.assertRaisesRegex(ContractViolation, "numeric"):
            validate_event({**VALID, "value": True})

    def test_rejects_timezone_free_timestamp(self) -> None:
        with self.assertRaisesRegex(ContractViolation, "timezone"):
            validate_event({**VALID, "occurred_at": "2026-01-01T00:00:00"})


if __name__ == "__main__":
    unittest.main()
