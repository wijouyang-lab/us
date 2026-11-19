# P8.1 Backtest Audit and Walk-forward

Date: 2026-11-08
Status: **P8_AUDIT_COMPLETE · WALK_FORWARD_COMPLETE · GO=0**

This report explains the P8 anomaly before changing any strategy conclusion.

## 1. Audit classification

| Finding | Class |
|---|---|
| 109 ticker symbols have one-day adjusted-close jumps >100% | **DATA_ISSUE** |
| CBE/ACS adjusted price levels switch between incompatible price bases | **DATA_ISSUE / BUG** |
| P8 full-period CAGR 41-51% was caused by those contaminated names | **DATA_ISSUE** |
| P8 HAC compared strategy net return with equal-weight net return | **VERIFIED** |
| Low Vol 60 positive Sharpe but negative HAC t | **VERIFIED** (different quantities) |
| P8 BH family was six equity strategies before ETF expansion | **METHODOLOGY_ISSUE** |
| Nasdaq-100 / Dow 30 intervals absent | **DATA_ISSUE / BLOCKED** |
| 2025-2026 historical price panel absent | **UNRESOLVED / BLOCKED** |
| Fundamental PIT backtest not yet run | **BLOCKED** |

## 2. Root cause of the 41-51% full-period CAGR

The raw panel has symbol/price contamination around corporate actions.

### CBE

```text
2006-05-01 entry adjusted open: 0.1535
2006-06-01 exit adjusted open:  0.1747   (normal)
next month entry:              18.8856
```

One month later the adjusted price changes by a factor of ~100 while the
underlying price series is the same security. The adjusted-close/raw-open
reconstruction is not consistent across the split/symbol event.

### ACS

```text
2009-09-30 close: 0.14, volume: 13,000
2009-10-01 open:  25.81, close: 28.70
2009-10-02 open:  0.15
```

The series alternates between a cent-price stub and a $25 price basis. This is
not a tradable return series.

CBE and ACS alone contributed +11.0 and +8.2 cumulative equal-weight units to
Momentum120.

### Corrected screen

Excluded 109 symbols with any one-day adjusted-close jump >100% (the list is in
`pit_strategy_results.json.data_issue.excluded_tickers`). This is deliberately
conservative and also removes some genuine merger/split names. It is a
**data-integrity filter**, not a performance filter.

After exclusion:

| Strategy | Original CAGR | Corrected CAGR | Original OOS | Corrected OOS |
|---|---:|---:|---:|---:|
| Momentum20 | 49.2% | **1.8%** | 3.1% | 3.3% |
| Momentum60 | 41.1% | **6.1%** | 6.1% | 5.8% |
| Momentum120 | 51.2% | **7.7%** | 10.1% | 9.2% |
| Trend MA200 | 50.0% | **6.9%** | 6.8% | 6.9% |
| Low Vol 60 | 11.0% | **9.3%** | 10.4% | 10.3% |
| Reversal 5 | 38.1% | **4.1%** | 6.2% | 6.5% |

Corrected coverage: **92.77%**, 298 months.

The original 41-51% CAGRs are rejected as data artifacts.

## 3. Statistical audit

- HAC Newey-West lag 6 on monthly returns: suitable for 12-month overlap-free
  monthly series, but only as a diagnostic.
- P8 equity HAC tests the mean **active return vs equal-weight**, not absolute
  return. Low Vol's positive Sharpe and negative active HAC are therefore not a
  contradiction: it compounded well in absolute terms but underperformed the
  equal-weight benchmark.
- Corrected Low Vol: absolute Sharpe 0.848, OOS 0.841, active HAC **-0.884**,
  BH q 0.377. NO-GO.
- The BH family now includes six equity + two ETF strategies; `bh_q_all` is the
  gate value. All 8 are >0.10.
- Missing months are removed, not zero filled; the monthly universe and
  benchmark are aligned by the same formation month.

## 4. Walk-forward

Implementation:

```text
60-month training
1-month purge
12-month test
strategy selected only on training Sharpe
19 test windows
```

Actual selected-strategy walk-forward:

```text
months: 228
CAGR: 8.66%
Sharpe: 0.576
max drawdown: -59.07%
HAC t vs zero: 2.294
p-value: 0.0218
```

The HAC t is positive versus zero, but:
- max drawdown -59% fails the -35% gate;
- it is not a test versus equal-weight;
- the selected strategy changes; no single fixed edge;
- no multiple-testing survival.

Walk-forward gate: **NO-GO**.

## 5. ETF defense re-evaluation

Trend risk and risk parity reduce drawdown vs SPY (-23% vs -51%), but:

- OOS CAGR 4.6% / 4.0% vs SPY 13.0%;
- OOS Sharpe 0.47 / 0.42 vs SPY 0.88;
- 2008/2020/2022 protection exists but does not create enough return;
- classification: **RISK MANAGEMENT, NOT ALPHA**; NO-GO for P8 shadow.

## 6. Fundamental strategies

P7.1 Value scores are current cross-sectional research, not a PIT historical
fundamental panel. No historical PIT fundamental backtest has been run.

Status:

```text
Value / Quality / GARP / Dividend / Growth historical PIT: DATA_BLOCKED
Current P7 Value research: available but not a P8 GO
```

Do not use current SEC facts as if they were available in 2000-2024.

## 7. Universe and current data

- S&P 500 effective-dated PIT: available.
- Nasdaq-100 interval: **DATA_BLOCKED**.
- Dow 30 interval: **DATA_BLOCKED**.
- 2025-2026 panel: not mixed with the 2000-2024 panel; current yfinance snapshot
  remains separate.

## 8. GO / NO-GO / DATA BLOCKED

```text
GO:              0
NO-GO:           8 strategies
DATA BLOCKED:    NDX membership, DJI membership, historical fundamental PIT,
                 2025-2026 historical panel
```

No P8 shadow is launched. P7 `RESEARCH_SHADOW_P7` remains independent and
pending; it is not evidence of P8 success.

## 9. Files

```text
data/research/p8/p8_audit.json
data/research/p8/pit_strategy_results.json
data/research/p8/pit_monthly_corrected.csv
data/research/p8/walk_forward_results.json
data/research/p8/etf_multiasset_results.json
data/research/p8/strategy_gate_results.csv
data/research/p8/p8_status.json
```

## 10. Remaining

- Obtain/verify NDX/DJI interval files.
- Build a genuine historical fundamental PIT panel; no current backfill.
- Extend 2025-2026 separately, not by concatenation.
- Run fixed-strategy walk-forward with train-only parameter selection and
  multiple-testing across all candidates.
- Event/macro feasibility, with no fabricated timestamps.
