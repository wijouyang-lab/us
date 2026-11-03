# F: VIX/VXV Backwardation Risk Filter

Date: 2026-11-03
Branch: `research/vix-term-structure-filter`
Status: **FAILED / NO-GO**

Research only. No Dashboard, broker integration, or orders.

## 1. Pre-registered rule

```text
vol_backwardation = VIXCLS > VXVCLS
```

| State | Allocation |
|---|---|
| Backwardation | BIL 100% |
| Normal | SPY 70%, IEF 15%, TLT 15% |
| Missing/invalid | BIL 100% |

Monthly at last SPY session; next SPY session raw Open. $50,000, long-only, no
leverage, 5 bps/leg base, 1/3/5/10/20 bps sensitivity. No VIX level filter, no
moving average, no other threshold.

## 2. PIT audit

| Item | Result |
|---|---|
| VIXCLS | FRED/ALFRED |
| VXVCLS | FRED/ALFRED |
| Common vintage | both series from same prior-SPY-session vintage |
| PIT decision dates | 153, 2014-01-31 to 2026-09-30 |
| Missing PIT pairs | 0 / 153 |
| Backwardation decisions | 10 |
| VXV pre-2014 | **exploratory only, not verified PIT** |
| Raw responses | per-decision SHA-256 in `pit_vix_vxv.csv`; payload not redistributed |

The pair is never mixed across vintages. A missing or invalid pair holds BIL.
The PIT sample cannot be extended before 2014 because both ALFRED series lack
common historical vintages; the 2007-12+ VXV observations are used only in the
exploratory sample.

## 3. Results at 5 bps/leg

### PIT: 2014-01-02 to 2026-10-30

| Metric | Value |
|---|---:|
| Final NAV | $122,879.32 |
| CAGR | 7.26% |
| Volatility | 10.13% |
| Sharpe | 0.74 |
| Max drawdown | **-25.84%** |
| Peak / trough / recovery | 2021-12-27 / 2022-11-03 / 2024-06-17 |
| Longest underwater | 620 sessions |
| Order legs | 410 |
| Total cost | $1,620.58 |
| Exposure | 92.4% |
| Backwardation decisions | 10 |
| Alpha vs BIL | +5.74%, p=0.029 |
| Alpha vs SPY | -6.68%, p=0.008 |
| Bootstrap CAGR 95% CI | +2.46% .. +12.90% |

### Exploratory: 2007-12-04 to 2026-10-30

| Metric | Value |
|---|---:|
| Final NAV | $166,354.23 |
| CAGR | 6.57% |
| Volatility | 10.23% |
| Sharpe | 0.67 |
| Max drawdown | **-27.36%** |
| Peak / trough / recovery | 2008-05-19 / 2009-04-02 / 2011-01-14 |
| Order legs | 632 |
| Total cost | $2,921.61 |
| Backwardation decisions | 21 |
| Alpha vs BIL | +5.58%, p=0.011 |
| Alpha vs SPY | -5.59%, p=0.025 |

State duration (monthly decisions):

| Sample | Backwardation | Normal | Total |
|---|---:|---:|---:|
| PIT | 10 | 143 | 153 |
| Exploratory | 21 | 206 | 227 |

Only one F rule was pre-registered, so there is no multi-rule BH family. HAC p-values are reported without a multiplicity discount. BIL/SPY benchmarks use total return with ex-date dividends, not price-only Close.

## 4. Stage-local results

### PIT

| Stage | CAGR / DD |
|---|---:|
| 2007-2015 | 5.15% / -9.03% |
| 2016-2020 | 9.37% / -14.93% |
| 2021-2026 | 6.57% / **-25.84%** |

### Exploratory

| Stage | CAGR / DD |
|---|---:|
| 2007-2015 | 5.10% / -27.36% |
| 2016-2020 | 9.39% / -14.94% |
| 2021-2026 | 6.58% / -25.87% |

## 5. Cost sensitivity

| Sample | 1 bps | 3 bps | 5 bps | 10 bps | 20 bps |
|---|---:|---:|---:|---:|---:|
| PIT CAGR | 7.39% | 7.32% | 7.26% | 7.11% | 6.81% |
| PIT MaxDD | -25.71% | -25.81% | -25.84% | -26.01% | -26.34% |
| Exploratory CAGR | 6.70% | 6.63% | 6.57% | 6.39% | 6.04% |
| Exploratory MaxDD | -27.17% | -27.27% | -27.36% | -27.59% | -28.10% |

Costs do not explain the failure.

## 6. Comparison

| Strategy | CAGR | Max DD |
|---|---:|---:|
| F PIT | 7.26% | -25.84% |
| F exploratory | 6.57% | -27.36% |
| E real-yield shock | 8.76% | -32.18% |
| D curve/NFCI exploratory | 8.42% | -24.27% |
| BIL | 1.40% | -0.78% |
| SPY | 10.56% | -55.19% |

F improves on E's drawdown but remains far above 15%. It does not dominate D on
return or risk.

## 7. Decision

| Gate | Result |
|---|---|
| Positive excess after costs | Yes |
| Statistical support vs BIL | Yes (PIT p=0.029) |
| Max DD <= 15% | **No (-25.84%)** |
| Not one stage | No: 2021-2026 dominates the failure |
| Enough exposure/trades | Yes |
| PIT reliable | Yes for 2014+ common vintages |
| Reproducible accounting | Yes |

**F = FAILED / NO-GO.** No parameter changed; no threshold rescue.

## 8. Tests and artifacts

`tests/test_vix_term_structure.py` covers same-vintage pairing, prior-session
lag, `VIX > VXV` state, missing-pair BIL, cutoff injection, raw Open, dividend
accounting, and total-return benchmarks.

```text
docs/research/VIX_TERM_STRUCTURE_F_PREREG.md
docs/research/VIX_TERM_STRUCTURE_F_RESULTS.md
docs/research/vix_term_structure/results.json
docs/research/vix_term_structure/nav_pit_2014_2026.csv
docs/research/vix_term_structure/nav_exploratory_2007_2026.csv
docs/research/vix_term_structure/trades_pit_2014_2026.csv
docs/research/vix_term_structure/trades_exploratory_2007_2026.csv
docs/research/vix_term_structure/events_pit_2014_2026.csv
docs/research/vix_term_structure/events_exploratory_2007_2026.csv
data/research/vix_term_structure/VIXCLS.csv
data/research/vix_term_structure/VXVCLS.csv
data/research/vix_term_structure/pit_vix_vxv.csv
data/research/vix_term_structure/manifest.json
data/research/vix_term_structure/{SPY,IEF,TLT,BIL}.csv
tools/research/vix_term_structure.py
tests/test_vix_term_structure.py
```
