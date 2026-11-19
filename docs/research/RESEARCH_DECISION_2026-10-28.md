# Research Decision: Freeze Full-History PIT Strategy Validation

Date: 2026-10-28
Research only. No production changes.

## Evidence snapshot

### Qlib research

- Qlib 0.9.7 was actually imported and run.
- Fixed Ridge model on the 2y PIT snapshot:
  - annualized net 39.85%, Sharpe 2.78, 9 test months.
- Walk-forward refit with 21-session purge:
  - annualized net 13.24%, Sharpe 0.69, t 0.64, max drawdown -11.88%.
- The fixed result did not survive walk-forward; 9 independent test months are
  insufficient.

### Data coverage

- 2y PIT snapshot: 222,388 rows, 502 tickers, 462 dates.
- 10y panel: 1,233,984 rows, 503 current-universe tickers.
- PIT member-session coverage: 91.61% (1,171,451 / 1,278,758).
- Ticker coverage at 90%: 84.23% (593 / 704).
- 98 tickers failed price refresh.
- 10y panel is current-universe and cannot represent the historical S&P 500.

### 98 missing tickers

Classification (full CSV in PR #390):

- 1 ticker (`PARA`) exists in the current SEC ticker map but its price request
  failed.
- 97 tickers have no exact match in the current SEC ticker map after alias
  lookup. That is **not** proof of delisting; it requires filing/announcement
  verification. The observed Yahoo 404 / "possibly delisted" errors and failed
  Wayback fallback are consistent with delisted/acquired/renamed status but do
  not establish it individually.

### Free source probes

| Source | Result |
|---|---|
| SEC company tickers | 10,429 records; identity/filings only; 1/98 current match |
| Stooq CSV | returned a 796-byte JavaScript challenge, no rows |
| Nasdaq quote/historical API | 0 historical records for AAPL/AVB/ATVI in the tested range; not usable as a source |
| Internet Archive | 0/98 recovered |
| OpenBB | no installed provider stack; no credentials; no independent request |\n| Alpha Vantage | adapter added; no key configured; all probes SKIPPED_NO_API_KEY |
| Yahoo | existing source; re-reading is not independent |

## Decision

1. **Freeze full-history PIT strategy validation.** Existing evidence is
   insufficient, and continuing model/factor search on the current panel would
   optimize around survivorship and missing-data bias.
2. **Do not resume production strategy work.**
3. Keep the current-universe research as an explicitly isolated exploratory
   track only. It cannot be used for production decisions.
4. Keep PR #389 (Qlib/walk-forward) and PR #390 (data coverage) as the research
   record. Do not merge them as evidence of deployable alpha.

## Minimum conditions to unblock

- Member-session bar coverage >= 95%
  - current: 1,171,451 / 1,278,758
  - minimum: 1,214,820
  - additional bars needed: **43,369**
- Ticker coverage at 90% >= 98%
  - current: 593
  - minimum: 690
  - additional qualifying tickers needed: **97**
- Delisted/acquired membership history with verifiable source and corporate
  actions; current independent recovery: 0/98.
- Independent source for OHLCV on matched dates, with Close difference
  <= 0.5% after adjustment.
- PIT timestamps for features and labels; no future availability.
- At least 12 independent non-overlapping out-of-sample windows with positive,
  cost-adjusted, benchmark-adjusted evidence.

Until these are met:

> **Free data in this environment is insufficient to support a deployable
> low-frequency strategy; current conclusion is no deployable alpha.**

## What remains valid

- Reproducible data audit and ticker classification.
- Qlib installation/import and fixed/walk-forward audit.
- Negative evidence: the fixed Sharpe does not survive honest refits.
- No production scanner, scoring, stop-loss, ledger, or trigger changes.
