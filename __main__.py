"""Command line entry point: python -m slo_calculator <data.csv> [options]"""
from __future__ import annotations

import argparse
import sys

from .core import analyze, load_csv
from .report import to_json, to_markdown


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="slo_calculator",
        description="Compute SLO compliance, error budget and burn-rate alerts from request counts.")
    ap.add_argument("csv", help="CSV with columns: timestamp,total_requests,failed_requests")
    ap.add_argument("--slo", type=float, default=99.9, help="SLO target in percent (default 99.9)")
    ap.add_argument("--window-days", type=float, default=30, help="SLO window in days (default 30)")
    ap.add_argument("-o", "--output", help="write the Markdown report to this file (default: print)")
    ap.add_argument("--json", dest="json_path", help="also write a JSON summary to this file")
    ap.add_argument("--fail-if-slo-missed", action="store_true",
                    help="exit with code 2 if the SLO was not met (useful in scripts and CI)")
    args = ap.parse_args(argv)

    try:
        rows = load_csv(args.csv)
        analysis = analyze(rows, args.slo, args.window_days)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    report = to_markdown(analysis, args.csv)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(report)
        print(f"Report written to {args.output}")
    else:
        print(report)
    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as handle:
            handle.write(to_json(analysis, args.csv))
    return 2 if (args.fail_if_slo_missed and not analysis.slo_met) else 0


if __name__ == "__main__":
    sys.exit(main())
