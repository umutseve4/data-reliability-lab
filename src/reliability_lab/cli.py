"""Command-line interface for running and inspecting the lab."""

from __future__ import annotations

import argparse
import json

from .pipeline import ingest_jsonl, replay_quarantine
from .reporting import write_report


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="reliability-lab")
    sub = root.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="ingest a JSONL file")
    run.add_argument("--source", required=True)
    run.add_argument("--db", default="artifacts/lab.db")
    run.add_argument("--fail-after", type=int)

    replay = sub.add_parser("replay", help="retry pending quarantine rows")
    replay.add_argument("--db", default="artifacts/lab.db")

    report = sub.add_parser("report", help="write a JSON reliability report")
    report.add_argument("--db", default="artifacts/lab.db")
    report.add_argument("--output", default="artifacts/reliability-report.json")
    report.add_argument("--quarantine-slo", type=float, default=0.05)
    return root


def main() -> int:
    args = parser().parse_args()
    if args.command == "run":
        result = ingest_jsonl(args.source, args.db, fail_after=args.fail_after)
        print(json.dumps(result.as_dict(), sort_keys=True))
    elif args.command == "replay":
        print(json.dumps(replay_quarantine(args.db), sort_keys=True))
    else:
        report = write_report(args.db, args.output, quarantine_slo=args.quarantine_slo)
        print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
