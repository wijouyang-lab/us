# D: Yield Curve + Financial Conditions Allocation

Date: 2026-11-03
Branch: `research/macro-curve-financial-conditions`
Status: **FAILED / NO-GO**

Research only. No Dashboard, broker integration, or orders.

## 1. Pre-registered rule

Frozen in `docs/research/MACRO_CURVE_D_PREREG.md` before the run.

```text
curve_inverted = T10Y3M < 0
financial_tight = NFCI > 0
```

| State | Allocation |
|---|---|
| Normal: curve >=0, NFCI <=0 | SPY 70%, IEF 15%, TLT 15% |
| Late cycle: curve <0, NFCI <=0 | IEF 40%, TLT 30%, SPY 15%, BIL 15% |
| Tight: curve >=0, NFCI >0 | IEF 30%, TLT 20%, BIL 50% |
| Stress: curve <0, NFCI >0 | BIL 100% |

Monthly at the last SPY session; next session raw Open; long-only, no leverage;
$50,000; IBKR Pro Tiered simulation; 5 bps/leg base; 1/3/5/10/20 bps sensitivity.
No threshold search or alternate state map was run.

## 2. PIT data audit

| Series | PIT source | PIT coverage | Use |
|---|---|---|---|
| T10Y3M | FRED + ALFRED vintages | 2014-01-27 to 2026-09-28 | **PIT_UNVERIFIED** |
| NFCI | FRED + ALFRED vintages | 2014-01-27 to 2026-09-28 | **PIT_UNVERIFIED** |
| NFCICREDIT | FRED current | not independently PIT-audited | not used |
| BAMLH0A0HYM2 | FRED current | only 2023-11-03 onward (792 rows) | **not used** |

PIT method:

- One ALFRED vintage probe per month, using the last **Monday** on/before month-end.
- These probes are conservative availability upper bounds, not verified actual
  release timestamps. The exact historical release time (08:30 ET vs holiday
  Thursday) was not independently recorded for every date.
- Therefore T10Y3M and NFCI are marked **PIT_UNVERIFIED** for this study, and no
  result is presented as verified point-in-time evidence.
- NFCI official schedule is Wednesday 08:30 ET, data through the prior Friday;
  a federal holiday on Wednesday or earlier normally moves it to Thursday. This
  rule was verified on the Chicago Fed page, but it is not a substitute for a
  historical release timestamp.
- ALFRED vintages handle revisions, but they do not by themselves prove the
  actual publication minute.
- ALFRED coverage begins 2014-01-27. **2007-2013 is not point-in-time** and is
  reported only as exploratory revised-history evidence.
- `BAMLH0A0HYM2` is explicitly rejected for long-sample use because FRED current
  history starts 2023-11-03. No backfill was fabricated.

Benchmark convention: BIL/SPY HAC benchmarks use total return with ex-date dividends included; before this correction they used price-only Close. PIT alpha changed 8.22% -> 6.43%; exploratory 8.53% -> 7.14%. Max drawdown and NO-GO are unchanged. Only one D rule was pre-registered, so no BH family correction is applied.

Raw/current and PIT SHA-256 records: `data/research/macro_d/manifest.json`.

## 3. Results

### 2014+ vintage-date sample (PIT_UNVERIFIED): 2014-02-03 to 2026-10-30

| Metric | Value |
|---|---:|
| Final NAV | $133,483.64 |
| CAGR | 8.01% |
| Volatility | 10.13% |
| Sharpe | 0.81 |
| Max drawdown | **-24.24%** |
| Peak / trough / recovery | 2021-12-27 / 2022-10-14 / 2026-05-06 |
| Order legs | 447 |
| Total cost | $1,141.32 |
| Alpha vs BIL (HAC) | +6.43%, p=0.0184 |
| Alpha vs SPY (HAC) | -6.45%, p=0.0102 |
| CAGR bootstrap 95% CI | +2.02% to +13.96% |

### Exploratory revised history: 2007-05-30 to 2026-10-30

| Metric | Value |
|---|---:|
| Final NAV | $240,210.41 |
| CAGR | 8.42% |
| Volatility | 9.46% |
| Sharpe | 0.90 |
| Max drawdown | **-24.27%** |
| Peak / trough / recovery | 2021-12-27 / 2022-10-14 / 2026-01-12 |
| Order legs | 686 |
| Total cost | $1,776.13 |
| Alpha vs BIL (HAC) | +7.14%, p=0.0002 |
| Alpha vs SPY (HAC) | -3.45%, p=0.248 |

The strategy has statistically strong BIL alpha in both samples, but the
2022 drawdown is far outside the 15% limit in both. This is not a borderline
result.

### Stage-local drawdown

| Stage | PIT CAGR / DD | Exploratory CAGR / DD |
|---|---:|---:|
| 2007-2013 | n/a (no PIT) | 9.37% / -9.56% |
| 2014-2019 | 9.66% / -12.60% | 9.66% / -12.60% |
| 2020-2026 | 6.41% / -24.27% | 6.41% / -24.27% |

The failure is concentrated in 2020-2026, specifically the 2022 rate shock. The
strategy did not de-risk fast enough because the curve/NFCI state remained
risk-on into the drawdown.

### Slippage sensitivity

| Sample | 1 bps | 3 bps | 5 bps | 10 bps | 20 bps |
|---|---:|---:|---:|---:|---:|
| PIT CAGR | 8.15% | 8.07% | 8.01% | 7.90% | 7.67% |
| PIT MaxDD | -24.23% | -24.24% | -24.24% | -24.24% | -24.26% |
| Exploratory CAGR | 8.46% | 8.45% | 8.42% | 8.36% | 8.24% |
| Exploratory MaxDD | -24.26% | -24.26% | -24.27% | -24.27% | -24.30% |

Costs do not explain the failure; drawdown is the blocker.

## 4. Decision

| Gate | Result |
|---|---|
| Positive excess after costs | Yes |
| Statistical support vs BIL | Yes (PIT p=0.0184) |
| Max DD <= 15% | **No (-24.24%)** |
| Not one stage | No: 2022 dominates the risk failure |
| Enough trades/exposure | Yes |
| Reproducible NAV/orders | Yes |
| Failures documented | Yes |

**D is FAILED / NO-GO.** It cannot be promoted by changing slippage, threshold,
or the 15% risk limit. The rule is not deployable.

## 5. What would be required next

A new pre-registered hypothesis must address why the 2022 inflation shock was
not captured, without retrofitting thresholds. Candidate directions include
explicit inflation/real-yield state or a drawdown throttle, but these are new
strategies and were **not** tested here.

## 6. Artifacts

```text
data/research/macro_d/
  T10Y3M.csv, NFCI.csv, NFCICREDIT.csv, BAMLH0A0HYM2.csv
  pit_T10Y3M.csv, pit_NFCI.csv, manifest.json
  SPY.csv, IEF.csv, TLT.csv, BIL.csv
docs/research/macro_d/results.json
docs/research/macro_d/nav_pit_2014_2026.csv
docs/research/macro_d/nav_exploratory_2007_2026.csv
docs/research/macro_d/trades_pit_2014_2026.csv
docs/research/macro_d/trades_exploratory_2007_2026.csv
docs/research/MACRO_CURVE_D_PREREG.md
tools/research/macro_curve_allocation.py
```
