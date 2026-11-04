import csv
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from slo_calculator.core import Row, analyze, load_csv

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
STEP = timedelta(minutes=5)
SAMPLE = os.path.join(os.path.dirname(__file__), "..", "sample_data", "requests_30d.csv")


def make_rows(count, total=1000, errors=0, overrides=None):
    """`count` five-minute rows; `overrides` maps row index -> failed requests."""
    overrides = overrides or {}
    return [Row(T0 + STEP * i, total, overrides.get(i, errors)) for i in range(count)]


def write_csv(text):
    handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="")
    handle.write(text)
    handle.close()
    return handle.name


class BudgetMathTests(unittest.TestCase):
    def test_budget_consumed_and_remaining(self):
        # 1,000 rows x 1,000 requests = 1,000,000 requests. SLO 99.9% allows 1,000 failures.
        rows = make_rows(1000, errors=0, overrides={i: 5 for i in range(50)})   # 250 failures
        a = analyze(rows, 99.9, window_days=30)
        self.assertEqual(a.total, 1_000_000)
        self.assertEqual(a.errors, 250)
        self.assertAlmostEqual(a.budget_events, 1000.0)
        self.assertAlmostEqual(a.budget_consumed, 0.25)
        self.assertAlmostEqual(a.budget_remaining, 0.75)
        self.assertTrue(a.slo_met)

    def test_exactly_on_slo_burns_at_1x(self):
        a = analyze(make_rows(500, total=1000, errors=1), 99.9)   # 0.1% failures
        self.assertAlmostEqual(a.availability, 0.999)
        self.assertAlmostEqual(a.overall_burn, 1.0)
        self.assertAlmostEqual(a.budget_consumed, 1.0)

    def test_slo_missed_and_exhausted(self):
        a = analyze(make_rows(500, total=1000, errors=5), 99.9)   # 0.5% failures
        self.assertFalse(a.slo_met)
        self.assertGreater(a.budget_consumed, 1.0)
        self.assertEqual(a.hours_until_exhausted, 0.0)

    def test_downtime_equivalent(self):
        a = analyze(make_rows(288 * 30, total=1000, errors=0), 99.9, window_days=30)
        self.assertAlmostEqual(a.allowed_downtime_min, 43.2, places=1)   # 0.1% of 30 days
        self.assertEqual(a.used_downtime_min, 0.0)

    def test_window_keeps_only_the_most_recent_days(self):
        rows = make_rows(288 * 40, total=1000, errors=0, overrides={0: 1000})  # failure on day 1 only
        a = analyze(rows, 99.9, window_days=30)
        self.assertEqual(a.errors, 0)                 # day 1 is outside the 30-day window
        self.assertAlmostEqual(a.window_days, 30.0)

    def test_current_burn_rate(self):
        a = analyze(make_rows(600, total=1000, errors=2), 99.9)     # 0.2% failures = 2x burn
        self.assertAlmostEqual(a.current_burn["1h"], 2.0)
        self.assertAlmostEqual(a.current_burn["6h"], 2.0)

    def test_no_recent_failures_means_budget_not_being_spent(self):
        rows = make_rows(600, total=1000, errors=0, overrides={10: 50})
        a = analyze(rows, 99.9)
        self.assertIsNone(a.hours_until_exhausted)


class AlertTests(unittest.TestCase):
    def test_healthy_service_fires_nothing(self):
        self.assertEqual(analyze(make_rows(600, errors=0), 99.9).alerts, [])

    def test_sudden_outage_fires_the_fast_burn_page(self):
        rows = make_rows(600, total=1000, errors=0, overrides={i: 500 for i in range(300, 306)})
        pages = [e for e in analyze(rows, 99.9).alerts if e.rule.severity == "page"]
        self.assertTrue(any(e.rule.burn == 14.4 for e in pages))
        fast = [e for e in pages if e.rule.burn == 14.4][0]
        self.assertEqual(fast.fired, T0 + STEP * 301)       # first failing bucket ends here

    def test_brief_blip_does_not_page(self):
        rows = make_rows(600, total=1000, errors=0, overrides={300: 20})   # one 2% bucket
        self.assertEqual([e for e in analyze(rows, 99.9).alerts if e.rule.severity == "page"], [])

    def test_slow_burn_creates_a_ticket_but_no_page(self):
        # 0.5% failures for 3 days is a 5x burn: above the 3x ticket rule, below the 6x page rule.
        rows = make_rows(288 * 10, total=1000, errors=0, overrides={i: 5 for i in range(1000, 1864)})
        alerts = analyze(rows, 99.9).alerts
        self.assertTrue(any(e.rule.severity == "ticket" for e in alerts))
        self.assertFalse(any(e.rule.severity == "page" for e in alerts))


class CsvTests(unittest.TestCase):
    def test_loads_valid_csv_with_z_suffix(self):
        path = write_csv("timestamp,total_requests,failed_requests\n"
                         "2026-01-01T00:00:00Z,100,1\n2026-01-01T00:05:00Z,100,0\n")
        rows = load_csv(path)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].ts, T0)
        os.unlink(path)

    def test_rejects_missing_columns(self):
        path = write_csv("time,count\n1,2\n3,4\n")
        with self.assertRaises(ValueError):
            load_csv(path)
        os.unlink(path)

    def test_rejects_more_failures_than_requests(self):
        path = write_csv("timestamp,total_requests,failed_requests\n"
                         "2026-01-01T00:00:00Z,10,11\n2026-01-01T00:05:00Z,10,0\n")
        with self.assertRaises(ValueError):
            load_csv(path)
        os.unlink(path)

    def test_rejects_unsorted_timestamps(self):
        path = write_csv("timestamp,total_requests,failed_requests\n"
                         "2026-01-01T00:05:00Z,10,0\n2026-01-01T00:00:00Z,10,0\n")
        with self.assertRaises(ValueError):
            load_csv(path)
        os.unlink(path)

    def test_rejects_invalid_slo(self):
        with self.assertRaises(ValueError):
            analyze(make_rows(10), 100.0)


class SampleDataTests(unittest.TestCase):
    def test_sample_data_story(self):
        a = analyze(load_csv(SAMPLE), 99.9, 30)
        self.assertEqual(a.total, 43_205_846)
        self.assertEqual(a.errors, 39_978)
        self.assertTrue(a.slo_met)
        self.assertAlmostEqual(a.budget_consumed, 0.925, places=2)
        first = a.alerts[0]
        self.assertEqual((first.rule.severity, first.rule.burn), ("page", 14.4))
        self.assertEqual(first.fired.date().isoformat(), "2026-09-24")
        self.assertEqual(a.worst_hours[0].start.date().isoformat(), "2026-09-24")
        self.assertTrue(any(e.rule.burn == 3.0 and e.fired.date().isoformat() == "2026-10-03"
                            for e in a.alerts))


if __name__ == "__main__":
    unittest.main()
