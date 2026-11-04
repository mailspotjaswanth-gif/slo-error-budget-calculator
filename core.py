"""Load request counts, compute SLO compliance, error budget, burn rates and alerts.

Input is a CSV with one row per fixed time step (5 minutes works well):

    timestamp,total_requests,failed_requests
    2026-09-14T00:00:00Z,4210,1
"""
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple


@dataclass
class Row:
    ts: datetime
    total: int
    errors: int


@dataclass(frozen=True)
class Rule:
    severity: str
    burn: float
    long_min: int
    short_min: int

    @property
    def label(self) -> str:
        return f"{self.burn:g}x over {fmt_minutes(self.long_min)} and {fmt_minutes(self.short_min)}"


# Multiwindow, multi-burn-rate alert rules in the style described in Google's SRE Workbook.
# An alert fires only when BOTH the long and the short window burn faster than the threshold:
# the long window proves it matters, the short window proves it is still happening.
RULES = [
    Rule("page", 14.4, 60, 5),
    Rule("page", 6.0, 360, 30),
    Rule("ticket", 3.0, 1440, 120),
    Rule("ticket", 1.0, 4320, 360),
]


def fmt_minutes(minutes: int) -> str:
    if minutes % 1440 == 0:
        return f"{minutes // 1440}d"
    if minutes % 60 == 0:
        return f"{minutes // 60}h"
    return f"{minutes}m"


def parse_ts(text: str) -> datetime:
    text = text.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    ts = datetime.fromisoformat(text)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def load_csv(path: str) -> List[Row]:
    needed = {"timestamp", "total_requests", "failed_requests"}
    rows: List[Row] = []
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not needed.issubset(set(reader.fieldnames)):
            raise ValueError("CSV must have the columns: timestamp,total_requests,failed_requests")
        for line_no, rec in enumerate(reader, start=2):
            try:
                ts = parse_ts(rec["timestamp"])
                total = int(rec["total_requests"])
                errors = int(rec["failed_requests"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"line {line_no}: {exc}") from exc
            if total < 0 or errors < 0 or errors > total:
                raise ValueError(f"line {line_no}: need 0 <= failed_requests <= total_requests")
            rows.append(Row(ts, total, errors))
    if len(rows) < 2:
        raise ValueError("need at least two data rows")
    for a, b in zip(rows, rows[1:]):
        if b.ts <= a.ts:
            raise ValueError(f"timestamps must increase; problem after {a.ts.isoformat()}")
    return rows


def infer_step(rows: List[Row]) -> timedelta:
    diffs = Counter(b.ts - a.ts for a, b in zip(rows, rows[1:]))
    return diffs.most_common(1)[0][0]


@dataclass
class AlertEpisode:
    rule: Rule
    fired: datetime
    ended: datetime
    peak_burn: float


@dataclass
class BurnPeriod:
    start: datetime
    end: datetime
    total: int
    errors: int
    budget_share: float


@dataclass
class DayStat:
    day: date
    total: int
    errors: int
    budget_share: float

    @property
    def availability(self) -> float:
        return 1 - self.errors / self.total if self.total else 1.0


@dataclass
class WeekStat:
    index: int
    start: datetime
    errors: int
    cumulative_share: float


@dataclass
class Analysis:
    slo: float
    window_days: float
    start: datetime
    end: datetime
    step_minutes: float
    total: int
    errors: int
    availability: float
    budget_events: float
    budget_consumed: float          # fraction, can exceed 1.0
    allowed_downtime_min: float
    used_downtime_min: float
    overall_burn: float
    current_burn: Dict[str, Optional[float]] = field(default_factory=dict)
    hours_until_exhausted: Optional[float] = None
    alerts: List[AlertEpisode] = field(default_factory=list)
    worst_hours: List[BurnPeriod] = field(default_factory=list)
    worst_days: List[DayStat] = field(default_factory=list)
    weeks: List[WeekStat] = field(default_factory=list)

    @property
    def slo_met(self) -> bool:
        return self.availability >= self.slo

    @property
    def budget_remaining(self) -> float:
        return 1.0 - self.budget_consumed


def analyze(rows: List[Row], slo_percent: float = 99.9, window_days: float = 30) -> Analysis:
    if not 0 < slo_percent < 100:
        raise ValueError("SLO must be between 0 and 100 (for example 99.9)")
    step = infer_step(rows)
    step_min = step.total_seconds() / 60
    n_window = int(round(window_days * 1440 / step_min))
    if len(rows) > n_window:
        rows = rows[-n_window:]
    n = len(rows)
    slo = slo_percent / 100.0
    budget_rate = 1.0 - slo

    tot = [0]
    err = [0]
    for r in rows:
        tot.append(tot[-1] + r.total)
        err.append(err[-1] + r.errors)

    def buckets(minutes: int) -> int:
        return max(1, int(round(minutes / step_min)))

    def burn(end: int, length: int) -> Optional[float]:
        """Burn rate of the `length` buckets ending at index `end` (inclusive)."""
        start = end + 1 - length
        if start < 0:
            return None
        t = tot[end + 1] - tot[start]
        e = err[end + 1] - err[start]
        return (e / t) / budget_rate if t else 0.0

    total, errors = tot[-1], err[-1]
    availability = 1 - errors / total if total else 1.0
    budget_events = budget_rate * total
    consumed = errors / budget_events if budget_events else 0.0
    covered_min = n * step_min

    analysis = Analysis(
        slo=slo, window_days=covered_min / 1440,
        start=rows[0].ts, end=rows[-1].ts + step, step_minutes=step_min,
        total=total, errors=errors, availability=availability,
        budget_events=budget_events, budget_consumed=consumed,
        allowed_downtime_min=budget_rate * covered_min,
        used_downtime_min=(errors / total if total else 0.0) * covered_min,
        overall_burn=(errors / total) / budget_rate if total else 0.0,
    )

    # Current burn rate over standard look-back windows.
    for minutes in (60, 360, 1440, 4320):
        analysis.current_burn[fmt_minutes(minutes)] = burn(n - 1, buckets(minutes))

    # Projection: how long the remaining budget lasts at the last-24h error volume.
    day_len = min(n, buckets(1440))
    errors_last_day = err[n] - err[n - day_len]
    remaining = budget_events - errors
    if remaining <= 0:
        analysis.hours_until_exhausted = 0.0
    elif errors_last_day > 0:
        analysis.hours_until_exhausted = remaining / (errors_last_day / (day_len * step_min / 60))

    # Alerts: replay history and find when each rule would have fired.
    episodes: List[AlertEpisode] = []
    for rule in RULES:
        long_n, short_n = buckets(rule.long_min), buckets(rule.short_min)
        current: Optional[List] = None   # [first_idx, last_idx, peak]
        for i in range(long_n - 1, n):
            long_burn, short_burn = burn(i, long_n), burn(i, short_n)
            firing = (long_burn is not None and short_burn is not None
                      and long_burn >= rule.burn and short_burn >= rule.burn)
            if not firing:
                continue
            if current is not None and i - current[1] <= short_n:
                current[1] = i
                current[2] = max(current[2], long_burn)
            else:
                if current is not None:
                    episodes.append(AlertEpisode(rule, rows[current[0]].ts + step,
                                                 rows[current[1]].ts + step, current[2]))
                current = [i, i, long_burn]
        if current is not None:
            episodes.append(AlertEpisode(rule, rows[current[0]].ts + step,
                                         rows[current[1]].ts + step, current[2]))
    analysis.alerts = sorted(episodes, key=lambda a: (a.fired, a.rule.long_min))

    # Biggest 1-hour burns, non-overlapping.
    hour_n = min(n, buckets(60))
    candidates = sorted(((err[i + 1] - err[i + 1 - hour_n], i) for i in range(hour_n - 1, n)),
                        key=lambda c: (-c[0], c[1]))
    taken: List[Tuple[int, int]] = []
    for e, i in candidates:
        if e <= 0 or len(taken) == 3:
            break
        a, b = i + 1 - hour_n, i
        if all(b < ta or a > tb for ta, tb in taken):
            taken.append((a, b))
            t = tot[b + 1] - tot[a]
            analysis.worst_hours.append(BurnPeriod(
                rows[a].ts, rows[b].ts + step, t, e, e / budget_events if budget_events else 0.0))

    # Worst days (UTC).
    per_day: Dict[date, List[int]] = defaultdict(lambda: [0, 0])
    for r in rows:
        per_day[r.ts.date()][0] += r.total
        per_day[r.ts.date()][1] += r.errors
    days = [DayStat(d, v[0], v[1], v[1] / budget_events if budget_events else 0.0)
            for d, v in per_day.items() if v[1] > 0]
    days.sort(key=lambda d: (d.availability, d.day))
    analysis.worst_days = days[:5]

    # Budget consumed by week.
    per_week: Dict[int, int] = defaultdict(int)
    for r in rows:
        per_week[int((r.ts - rows[0].ts) / timedelta(days=7))] += r.errors
    running = 0
    for w in sorted(per_week):
        running += per_week[w]
        analysis.weeks.append(WeekStat(
            w + 1, rows[0].ts + timedelta(days=7 * w), per_week[w],
            running / budget_events if budget_events else 0.0))
    return analysis
