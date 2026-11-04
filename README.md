# SLO & Error Budget Calculator

A command line tool that turns raw request counts into the numbers a reliability team actually runs on: SLO compliance, how much **error budget** is left, how fast it is being spent (**burn rate**), and which alerts would have fired.

Pure Python standard library. No installs, no AWS account, no setup.

## The real-world problem

Teams promise customers an SLA ("99.9% uptime") but often cannot answer the questions that follow:

- Did we meet it this month, and by how much?
- Can we afford to ship a risky release, or should we stabilize first?
- Which outage cost us the most?
- Would our alerts have caught the problem in time, without paging people for noise?

This tool answers all four from a simple CSV of request counts, and applies the same multiwindow, multi-burn-rate alerting approach described in Google's SRE Workbook.

## Quick start

You need Python 3.9 or newer. Clone the repo (or download it as a ZIP), open a terminal in the repo folder, and run:

```bash
python3 -m slo_calculator sample_data/requests_30d.csv
```

To save the report and a JSON summary:

```bash
python3 -m slo_calculator sample_data/requests_30d.csv -o report.md --json summary.json
```

On Windows, use `python` instead of `python3` if that is how Python is installed.

## What the sample run finds

`sample_data/requests_30d.csv` holds 30 days of 5-minute request counts (43.2 million requests). **The data is synthetic**: `scripts/generate_sample_data.py` created it with three deliberately injected incidents so the tool has something to find. Full output: [`sample_output/SLO_REPORT.md`](sample_output/SLO_REPORT.md).

| Metric | Value |
|---|---|
| SLO target | 99.900% |
| Availability achieved | 99.9075% |
| SLO met | Yes |
| Error budget (failures allowed) | 43,206 |
| Budget consumed | 92.5% |
| Downtime allowed / used | 43.2 min / 40.0 min |

The headline is "SLO met", but the story underneath is that **92.5% of the budget is gone**, so the tool recommends slowing down risky changes. It also shows why:

- **Sept 24, 14:10 to 14:35 (dependency outage):** one hour with 14,735 failed requests ate **34.1% of the whole month's budget**. The fast-burn page rule (14.4x over 1h and 5m) fires at 14:15, five minutes in.
- **Oct 3 to 4 (slow degradation, 0.5% failures):** never bad enough to page, but the 3x ticket rule fires at 14:35 on Oct 3 and flags it. A plain "error rate above 1%" alert would have missed it completely.
- **Oct 9, 09:00 to 10:00 (bad config, 3% failures):** pages at 09:30.

## Key ideas

- **Error budget** = the failures your SLO allows. A 99.9% SLO over 43.2 million requests allows 43,206 failures.
- **Burn rate** = how fast you are spending it. 1x spends exactly the whole budget over the full window. 14.4x would burn 2% of a 30-day budget in a single hour.
- **Multiwindow alerts:** a rule fires only when both a long window (proves it matters) and a short window (proves it is still happening) exceed the threshold. That keeps alerts fast without paging for blips.

Alert rules used:

| Severity | Burn rate | Long window | Short window |
|---|---|---|---|
| page | 14.4x | 1 hour | 5 minutes |
| page | 6x | 6 hours | 30 minutes |
| ticket | 3x | 1 day | 2 hours |
| ticket | 1x | 3 days | 6 hours |

These are defined in `slo_calculator/core.py` (`RULES`) if you want to change them.

## Input format

A CSV with one row per fixed time step (5 minutes or finer is best, so the 5-minute window is exact):

```csv
timestamp,total_requests,failed_requests
2026-09-14T00:00:00Z,4210,1
2026-09-14T00:05:00Z,4188,2
```

`failed_requests` is whatever your SLO counts as bad, typically 5xx responses. Timestamps must be ISO 8601 and strictly increasing. Bad input produces a clear error with the line number.

## Options

| Option | Default | Meaning |
|---|---|---|
| `--slo` | 99.9 | SLO target in percent |
| `--window-days` | 30 | SLO window; only the most recent days of data are used |
| `-o`, `--output` | print | write the Markdown report to a file |
| `--json` | off | also write a JSON summary |
| `--fail-if-slo-missed` | off | exit with code 2 if the SLO was missed (for scripts and CI) |

## Tests

```bash
python3 -m unittest discover -s tests -t . -v
```

17 tests check the budget math by hand-computed examples, window trimming, burn rates, alert behavior (outage pages, blip does not, slow burn tickets without paging), CSV validation, and the sample data end to end. They run automatically on every push through GitHub Actions.

## Project layout

```
slo_calculator/      core.py (math and alert replay), report.py, __main__.py
scripts/             generate_sample_data.py (rebuilds the sample data)
sample_data/         synthetic requests_30d.csv
sample_output/       report and JSON produced from the sample data
tests/               unit tests
.github/workflows/   CI that runs the tests
```

## Skills demonstrated

SLI/SLO/SLA thinking, error budgets and release policy, burn-rate alerting, availability math and downtime equivalents, input validation, writing tested Python, CI with GitHub Actions.

## Limitations

- It works from aggregated request counts. It does not query Prometheus, CloudWatch or any monitoring system. Export your counts to CSV first.
- Availability is the only SLI. Latency SLOs would need a second "slow requests" column.
- Alert replay shows when a rule would have fired on historical data. It does not send notifications.

## License

MIT
