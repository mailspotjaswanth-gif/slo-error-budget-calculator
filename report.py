"""Markdown and JSON output for an SLO analysis."""
from __future__ import annotations

import json
from datetime import datetime

from .core import Analysis


def fmt_ts(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%d %H:%M UTC")


def fmt_hours(hours: float) -> str:
    if hours < 48:
        return f"{hours:.1f} hours"
    return f"{hours / 24:.1f} days"


def _bar(share: float) -> str:
    return "█" * min(25, int(round(share * 25)))


def _advice(remaining: float) -> str:
    if remaining <= 0:
        return ("The error budget is exhausted. Under a typical error budget policy, pause "
                "non-essential releases and put reliability work first until the budget recovers.")
    if remaining < 0.25:
        return ("Less than a quarter of the budget is left. Under a typical error budget policy, "
                "slow down risky changes and prioritize the fixes behind the biggest burns below.")
    if remaining < 0.5:
        return ("Less than half of the budget is left. Release as normal, but review the biggest "
                "burns and make sure their follow-up actions are done.")
    return "Plenty of budget left. Normal release pace is fine."


def to_markdown(a: Analysis, source: str) -> str:
    out = [
        "# SLO and error budget report", "",
        f"Source: `{source}`  ",
        f"Period: {fmt_ts(a.start)} to {fmt_ts(a.end)} ({a.window_days:.1f} days, "
        f"{a.step_minutes:g}-minute data)", "",
        "## SLO status", "",
        "| Metric | Value |", "|---|---|",
        f"| SLO target | {a.slo:.3%} |",
        f"| Availability achieved | {a.availability:.4%} |",
        f"| SLO met | {'Yes' if a.slo_met else 'No'} |",
        f"| Requests | {a.total:,} |",
        f"| Failed requests | {a.errors:,} |",
        f"| Error budget (failures allowed) | {a.budget_events:,.0f} |",
        f"| Budget consumed | {a.budget_consumed:.1%} |",
        f"| Budget remaining | {a.budget_remaining:.1%} |",
        f"| Downtime allowed by the SLO | {a.allowed_downtime_min:.1f} min |",
        f"| Downtime-equivalent used | {a.used_downtime_min:.1f} min |",
        f"| Average burn rate over the period | {a.overall_burn:.2f}x |",
        "",
        f"**{_advice(a.budget_remaining)}**", "",
        "## Current burn rate", "",
        "A burn rate of 1x spends exactly the whole budget over the full period. "
        "Higher means the budget runs out early.", "",
        "| Look-back window | Burn rate |", "|---|---:|",
    ]
    for window, value in a.current_burn.items():
        out.append(f"| last {window} | {'n/a' if value is None else f'{value:.2f}x'} |")
    if a.hours_until_exhausted is None:
        out += ["", "No failures in the last 24 hours, so the remaining budget is not being spent."]
    elif a.hours_until_exhausted == 0:
        out += ["", "The budget is already exhausted."]
    else:
        out += ["", f"At the failure volume of the last 24 hours, the remaining budget would last "
                    f"about {fmt_hours(a.hours_until_exhausted)}."]

    out += ["", "## Alerts that would have fired", "",
            "Replay of multiwindow, multi-burn-rate alert rules. A rule fires only when both its "
            "long and short windows exceed the burn rate.", ""]
    if a.alerts:
        out += ["| Severity | Rule | Fired | Cleared | Peak burn (long window) |",
                "|---|---|---|---|---:|"]
        for ep in a.alerts:
            out.append(f"| {ep.rule.severity} | {ep.rule.label} | {fmt_ts(ep.fired)} | "
                       f"{fmt_ts(ep.ended)} | {ep.peak_burn:.1f}x |")
    else:
        out.append("No alert rule would have fired.")

    out += ["", "## Biggest one-hour burns", "",
            "| Hour starting | Requests | Failed | Error rate | Share of whole budget |",
            "|---|---:|---:|---:|---:|"]
    for w in a.worst_hours:
        out.append(f"| {fmt_ts(w.start)} | {w.total:,} | {w.errors:,} | "
                   f"{w.errors / w.total:.2%} | {w.budget_share:.1%} |")

    out += ["", "## Worst days (UTC)", "",
            "| Day | Requests | Failed | Availability | Share of whole budget |",
            "|---|---:|---:|---:|---:|"]
    for d in a.worst_days:
        out.append(f"| {d.day.isoformat()} | {d.total:,} | {d.errors:,} | "
                   f"{d.availability:.3%} | {d.budget_share:.1%} |")

    out += ["", "## Budget consumed over time", "",
            "| Week | Starting | Failed | Cumulative budget used | |", "|---|---|---:|---:|---|"]
    for w in a.weeks:
        out.append(f"| {w.index} | {w.start.strftime('%Y-%m-%d')} | {w.errors:,} | "
                   f"{w.cumulative_share:.1%} | {_bar(w.cumulative_share)} |")
    out.append("")
    return "\n".join(out)


def to_json(a: Analysis, source: str) -> str:
    payload = {
        "source": source,
        "period_start": a.start.isoformat(),
        "period_end": a.end.isoformat(),
        "slo_target": a.slo,
        "availability": round(a.availability, 6),
        "slo_met": a.slo_met,
        "requests": a.total,
        "failed_requests": a.errors,
        "error_budget_events": round(a.budget_events, 1),
        "budget_consumed": round(a.budget_consumed, 4),
        "budget_remaining": round(a.budget_remaining, 4),
        "overall_burn_rate": round(a.overall_burn, 3),
        "current_burn_rates": {k: (None if v is None else round(v, 3))
                               for k, v in a.current_burn.items()},
        "hours_until_exhausted": a.hours_until_exhausted,
        "alerts": [{"severity": e.rule.severity, "rule": e.rule.label,
                    "fired": e.fired.isoformat(), "cleared": e.ended.isoformat(),
                    "peak_burn": round(e.peak_burn, 2)} for e in a.alerts],
    }
    return json.dumps(payload, indent=2)
