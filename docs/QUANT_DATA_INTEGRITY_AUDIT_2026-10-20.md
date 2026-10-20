# Quant Data Integrity Audit — 2026-10-20

## Scope and safety

This audit was computed from the Git-tracked files on `main` at commit `97d1de81c47d5944d31e884ea860e1ae341f8204`, using read-only file retrieval. The audit script added in this PR is `tools/research/audit_date_integrity.py`.

No CSV, price history, paper ledger, portfolio ledger, or trading workflow was executed or rewritten during this audit. The counts below describe repository files, not a live broker feed.

## Findings

### 1. Factor snapshot session dates

Input: `quant_factor_snapshot.csv` (blob `54af1a41ab8d6c52adca1c77c501131bcb186da0`)

| Check | Observed |
|---|---:|
| Snapshot rows | 2,506 |
| Scan_Date range | 2026-10-07 to 2026-10-19 |
| Technical_Date range | 2026-10-05 to 2026-10-18 |
| Technical_Date on Saturday/Sunday | **553 rows, all Sunday** |
| Duplicate (Scan_Date, uppercase Ticker) keys | 0 |
| Snapshot schema versions | 2,506 rows of `phase1.v1` |

Calendar-day distance `Scan_Date - Technical_Date` is +1 day for 1,351 rows, +2 days for 870 rows and +4 days for 285 rows. Different Scan_Date and Technical_Date values are not inherently an error: a scan may run before the session is complete or after a weekend/holiday. A Sunday `Technical_Date`, however, is not a valid US equity regular-session date and must not be silently accepted.

The affected rows must be treated as suspect historical observations. The source code fix prevents future naive daily-bar labels from being shifted by converting them as if they were UTC instants, but it does not retroactively repair these old rows.

### 2. Persistent OHLCV price history

Input: `quant_factor_price_history.csv` (blob `351eca8f3f899e6eb34aa4c71fe6a608267f5153`)

| Check | Observed |
|---|---:|
| Total rows | 56,128 |
| Distinct tickers | 444 |
| Date range | 2025-12-29 to 2026-10-18 |
| `phase2b.v2` rows | 52,242; latest date 2026-10-14 |
| `phase2b.v1` rows | **3,886**; dates span 2026-09-27 to 2026-10-18 |
| Weekend-labelled rows | **1,516**, all Sunday |
| Duplicate physical (Date, Ticker) keys | 0 |
| Missing/invalid Close values | 0 |

All 1,516 weekend labels belong to `phase2b.v1`; the `phase2b.v2` rows have no weekend labels. The legacy v1 dates have a weekday distribution of Sunday 1,516; Monday 543; Tuesday 543; Wednesday 543; Thursday 741; Friday 0; Saturday 0. This pattern is strongly consistent with the old timezone conversion shifting daily session labels back by one calendar day. The absence of duplicate physical keys does **not** rule out a logical overlap: the same actual session's bar can be stored under different dates in the two schema generations.

Code/data mismatch also exists on the inspected production baseline: `quant_factor_price.py` on `main` declares `SCHEMA_VERSION = phase2b.v1`, while the file is mixed between v1 and v2. The PR branch's writer uses v2. The PR branch's Paper Trading reader correctly fails closed unless the entire history is v2, while the currently inspected `main` reader does not validate the version column before consuming Date/Ticker/Close.

### 3. Intraday stop scheduling is not the documented cadence

The production `.github/workflows/dashboard-data.yml` contains an `--intraday-stop` call. Its current cron is `0 * * * 1-5` (hourly), although the workflow comment says every 15 minutes and the design document specifies 15-minute monitoring. The workflow also contains a stale top-level comment saying the dashboard workflow does not run stop logic. The actual stop step uses `continue-on-error: true`, so the workflow can complete even if that step fails.

The price helper in `portfolio_50000.py` calls `yfinance.Ticker(t).history(period="5d")` without explicitly selecting an intraday interval or using a dedicated quote API. This audit therefore does not certify that its `current` value is an exchange-grade real-time quote. The schedule frequency and the price freshness are separate reliability gaps; increasing trigger frequency alone would not prove quote freshness.

## Recommended repair sequence

1. Keep the session-date and schema checks fail-closed. Do not delete Sunday-labelled rows or shift all v1 dates in place: Sunday rows may represent Monday bars that were mislabeled, and weekday-labelled v1 rows may also be shifted.
2. Before a rebuild, preserve a versioned backup of the exact production CSV and produce a candidate corrected OHLCV file separately. Check the complete historical ticker universe (including renamed/delisted symbols), Date/Ticker uniqueness, valid session dates, Close/Open sanity, schema uniformity and row/date coverage.
3. Run the candidate through the date/schema audit and Paper Trading tests on temporary files. Compare representative v1 rows against independently downloaded daily bars before promoting any corrected file.
4. Only after the candidate passes should the data owner schedule a controlled historical rebuild and a separate paper-ledger replay plan. Do not replay over the existing paper ledger until the consequences for previously recorded fills are defined.
5. Separately resolve the stop workflow's hourly-vs-15-minute mismatch and quote-source freshness. Do not simply raise the whole dashboard workflow to every 15 minutes without reviewing its shared concurrency group with the portfolio review workflow.

## Rerun the audit

From the repository root:

```bash
python tools/research/audit_date_integrity.py
python tools/research/audit_date_integrity.py --strict
```

The default mode prints a JSON report and exits successfully so findings remain inspectable. `--strict` returns exit code 1 when integrity issues are present. Both modes are read-only.
