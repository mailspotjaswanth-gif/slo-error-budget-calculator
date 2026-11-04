"""Generate 30 days of synthetic 5-minute request counts with three injected incidents.

The data is fake. It exists so the calculator can be run immediately and tested.
Deterministic: the same seed always produces the same file.

Injected incidents (all UTC):
  1. 2026-09-24 14:10-14:35  dependency outage, 40% of requests fail  (fast burn)
  2. 2026-10-03 00:00 to 2026-10-04 12:00  slow degradation, 0.5% fail  (slow burn)
  3. 2026-10-09 09:00-10:00  bad config, 3% fail

Usage: python scripts/generate_sample_data.py [output_path]
"""
import csv
import math
import random
import sys
from datetime import datetime, timedelta, timezone

SEED = 7
START = datetime(2026, 9, 14, 0, 0, tzinfo=timezone.utc)
DAYS = 30
STEP = timedelta(minutes=5)
BASE_ERROR_RATE = 0.0003   # 0.03% background failures


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


INCIDENTS = [  # (start, end, failure rate)
    (utc(2026, 9, 24, 14, 10), utc(2026, 9, 24, 14, 35), 0.40),
    (utc(2026, 10, 3, 0, 0), utc(2026, 10, 4, 12, 0), 0.005),
    (utc(2026, 10, 9, 9, 0), utc(2026, 10, 9, 10, 0), 0.03),
]


def main(out_path):
    rng = random.Random(SEED)
    rows = []
    ts = START
    for _ in range(DAYS * 288):
        hour = ts.hour + ts.minute / 60
        traffic = 5000 * (1 + 0.45 * math.sin(2 * math.pi * (hour - 8) / 24))   # daily wave
        total = max(100, int(rng.gauss(traffic, traffic * 0.03)))
        rate = BASE_ERROR_RATE
        for start, end, incident_rate in INCIDENTS:
            if start <= ts < end:
                rate = incident_rate
        expected = total * rate
        errors = max(0, int(round(rng.gauss(expected, math.sqrt(max(expected, 1))))))
        rows.append((ts.strftime("%Y-%m-%dT%H:%M:%SZ"), total, min(errors, total)))
        ts += STEP
    with open(out_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp", "total_requests", "failed_requests"])
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "sample_data/requests_30d.csv")
