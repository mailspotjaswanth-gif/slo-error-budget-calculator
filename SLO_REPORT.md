# SLO and error budget report

Source: `sample_data/requests_30d.csv`  
Period: 2026-09-14 00:00 UTC to 2026-10-14 00:00 UTC (30.0 days, 5-minute data)

## SLO status

| Metric | Value |
|---|---|
| SLO target | 99.900% |
| Availability achieved | 99.9075% |
| SLO met | Yes |
| Requests | 43,205,846 |
| Failed requests | 39,978 |
| Error budget (failures allowed) | 43,206 |
| Budget consumed | 92.5% |
| Budget remaining | 7.5% |
| Downtime allowed by the SLO | 43.2 min |
| Downtime-equivalent used | 40.0 min |
| Average burn rate over the period | 0.93x |

**Less than a quarter of the budget is left. Under a typical error budget policy, slow down risky changes and prioritize the fixes behind the biggest burns below.**

## Current burn rate

A burn rate of 1x spends exactly the whole budget over the full period. Higher means the budget runs out early.

| Look-back window | Burn rate |
|---|---:|
| last 1h | 0.31x |
| last 6h | 0.32x |
| last 1d | 0.32x |
| last 3d | 0.33x |

At the failure volume of the last 24 hours, the remaining budget would last about 7.0 days.

## Alerts that would have fired

Replay of multiwindow, multi-burn-rate alert rules. A rule fires only when both its long and short windows exceed the burn rate.

| Severity | Rule | Fired | Cleared | Peak burn (long window) |
|---|---|---|---|---:|
| page | 14.4x over 1h and 5m | 2026-09-24 14:15 UTC | 2026-09-24 14:35 UTC | 168.9x |
| page | 6x over 6h and 30m | 2026-09-24 14:15 UTC | 2026-09-24 15:00 UTC | 31.1x |
| ticket | 1x over 3d and 6h | 2026-09-24 14:15 UTC | 2026-09-24 20:30 UTC | 3.7x |
| ticket | 3x over 1d and 2h | 2026-09-24 14:20 UTC | 2026-09-24 16:30 UTC | 10.5x |
| ticket | 1x over 3d and 6h | 2026-10-03 12:20 UTC | 2026-10-04 17:05 UTC | 2.5x |
| ticket | 3x over 1d and 2h | 2026-10-03 14:35 UTC | 2026-10-04 12:45 UTC | 5.0x |
| page | 14.4x over 1h and 5m | 2026-10-09 09:30 UTC | 2026-10-09 10:00 UTC | 28.9x |
| page | 6x over 6h and 30m | 2026-10-09 09:55 UTC | 2026-10-09 10:20 UTC | 6.6x |

## Biggest one-hour burns

| Hour starting | Requests | Failed | Error rate | Share of whole budget |
|---|---:|---:|---:|---:|
| 2026-09-24 14:05 UTC | 88,037 | 14,735 | 16.74% | 34.1% |
| 2026-10-09 09:00 UTC | 71,090 | 2,058 | 2.89% | 4.8% |
| 2026-10-03 11:45 UTC | 84,553 | 444 | 0.53% | 1.0% |

## Worst days (UTC)

| Day | Requests | Failed | Availability | Share of whole budget |
|---|---:|---:|---:|---:|
| 2026-09-24 | 1,442,396 | 15,145 | 98.950% | 35.1% |
| 2026-10-03 | 1,440,517 | 7,169 | 99.502% | 16.6% |
| 2026-10-04 | 1,435,853 | 3,365 | 99.766% | 7.8% |
| 2026-10-09 | 1,437,663 | 2,491 | 99.827% | 5.8% |
| 2026-10-12 | 1,438,872 | 491 | 99.966% | 1.1% |

## Budget consumed over time

| Week | Starting | Failed | Cumulative budget used | |
|---|---|---:|---:|---|
| 1 | 2026-09-14 | 3,149 | 7.3% | ██ |
| 2 | 2026-09-21 | 17,876 | 48.7% | ████████████ |
| 3 | 2026-09-28 | 12,786 | 78.3% | ████████████████████ |
| 4 | 2026-10-05 | 5,215 | 90.3% | ███████████████████████ |
| 5 | 2026-10-12 | 952 | 92.5% | ███████████████████████ |
