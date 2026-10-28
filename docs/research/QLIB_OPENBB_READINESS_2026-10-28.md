# Qlib / OpenBB Readiness Audit

Date: 2026-10-28
Research only. No production changes.

## Data audit

Command:

```bash
python tools/research/audit_lowfreq_data.py \
  --snapshot research_factor_snapshots_sp500_pit_2y.csv \
  --price-history research_price_history_sp500_10y.csv \
  --output research_lowfreq_data_audit.json
```

### PIT 2-year snapshot

- rows: 222,388
- tickers: 502
- technical dates: 462
- scan dates: 462
- range: 2024-12-09 to 2026-10-13
- duplicate `(Technical_Date, Ticker)`: 0
- invalid dates: 0
- weekend rows: 0
- non-positive Price: 0
- missing Price: 0
- `Scan_Date < Technical_Date`: 0
- schema: `phase1.v1`

Feature missing rates are at most 0.21% (`Momentum_60D_Pct` and
`Beta_60D_SPY`); the rest are complete in this panel.

### 10-year price panel

- rows: 1,233,984
- tickers: 503
- dates: 2,532
- range: 2016-09-19 to 2026-10-14
- duplicate `(Date, Ticker)`: 0
- invalid dates: 0
- weekend rows: 0
- non-positive Close: 0
- missing Close/Open/Volume: 0
- schema: `phase2b.v1`

**Critical limitation:** this is a current-universe panel. It does not contain
the delisted constituents needed for survivorship-free 10-year inference.

## Qlib compatibility

- `qlib` is not installed in the execution environment.
- Attempts to install `pyqlib` did not complete (package installation hung);
  no Qlib model or Qlib backtest was run.
- A neutral exporter is provided:
  `tools/research/export_qlib_panel.py`.
- Export result on the 2-year PIT snapshot:
  - 502 per-instrument CSV files
  - 18 exported feature columns
  - manifest with source SHA-256 and per-instrument row/date bounds
- This is a **Qlib-compatible input export**, not evidence that a Qlib model
  was trained or validated.

## OpenBB provider audit

OpenBB v4 documents historical equity providers:

```text
fmp, intrinio, polygon, tiingo, yfinance
```

Source: https://docs.openbb.co/odp/v4/cli/data-sources

OpenBB's FAQ states coverage depends on provider and subscription, and free
tiers are commonly US-listing only:
https://raw.githubusercontent.com/OpenBB-finance/OpenBB/27fb5cd23b34baeee5f918b8ff4e646a4837ad20/website/content/platform/faqs/data_providers.md

- `openbb` is not installed in this environment.
- No OpenBB live request was made.
- No provider API keys are available in this research environment.
- `yfinance` is already the underlying source used by the existing panel.
- Free `yfinance` cannot be assumed to provide the 98 missing delisted tickers.

## What is blocked

The following cannot be claimed from this run:

1. A Qlib-trained baseline or candidate model.
2. A Qlib backtest with costs and turnover.
3. OpenBB multi-source price reconciliation.
4. Any improvement to 10-year delisted coverage.

## What is ready

- Reproducible read-only data audit.
- Qlib-compatible per-instrument export with manifest and source hash.
- Explicit provider limits and install/absence status.
- No silent filling, no interpolation, no production writes.

## Required unblock

One of:

- Qlib package installation from a working package source;
- OpenBB installation plus documented free-provider credentials;
- or an approved paid/alternative source for delisted history.

Until then, no model result should be presented as validated.
