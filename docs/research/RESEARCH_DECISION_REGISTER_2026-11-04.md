# Research Decision Register — 2026-11-04

Project: `wijouyang-lab/us`  
Scope: research branches only. No production changes, no broker integration, no orders.

**CI green is not evidence of alpha.** Every GO/NO-GO below is based on the
strategy's own return, risk, cost, data and statistical evidence.

---

## 1. Status summary

### Frozen NO-GO (completed research)

- A/B/C low-frequency ETF comparison
- D yield-curve / NFCI allocation
- E real-yield shock filter
- F VIX/VXV backwardation filter
- QQQ Transition
- Qlib-inspired composite
- Qlib Ridge baseline (insufficient observations)
- Five-factor low-frequency validation
- Formula factor screen

### Passive risk baseline only

- G fixed 20% QQQ / 80% BIL

### Blocked / insufficient data

- PIT macro/event audit
- Qlib/OpenBB independent data readiness

---

## 2. Decision table

| Research | PR | HEAD | Status | Best reliable result | Cost basis | Data limits | OOS | Statistics | Decision | Resume condition |
|---|---|---|---|---|---|---|---|---|---|---|
| A dual momentum | #451 | `a5188c4` | NO-GO | CAGR 6.21%, MaxDD -25.59%, vol 13.5% | old IBKR approx, 5 bps | ETF survivorship; adjusted prices | none | BIL alpha q=.065 | FAILED: DD >15% | Lower-risk implementation with no parameter rescue, PIT universe |
| B trend/vol | #451 | `a5188c4` | NO-GO | CAGR 6.59%, MaxDD -15.20%, vol 8.8% | old IBKR approx, 5 bps | same | none | BIL alpha q=.006 | FAILED: DD 15.20% | Cannot resume by cost change; risk gate failed by 0.20pp |
| C QQQ Transition sleeve | #451 | `a5188c4` | NO-GO | CAGR 1.94%, MaxDD -5.52% | old IBKR approx, 5 bps | same | QQQ prior study | BIL q=.094 | FAILED: insufficient alpha | Only with independent OOS and no re-tune |
| D curve/NFCI | #452 | `9db7a88` | NO-GO | PIT 2014+ CAGR 8.01%, MaxDD -24.24%; exploratory 8.42% | calibrated-ish $1,141 | NFCI/T10Y3M **PIT_UNVERIFIED**; pre-2014 not PIT | no | BIL excess +6.61%, p=.015 | FAILED: DD >15% | Actual historical release timestamps, then new prereg |
| E real-yield shock | #453 | `8f97d40` | NO-GO | CAGR 8.76%, MaxDD -32.18%, vol 11.2% | new-ish $3,864 | DFII10 PIT 2007+; VXV none | no | BIL excess +7.80%, p=.0007 | FAILED: DD >15% | New state design, not threshold/window tuning |
| F VIX/VXV | #454 | `d1a01ed` | NO-GO | PIT CAGR 7.06%, MaxDD -25.83%; exploratory 6.57% | old approx $1,495 | common ALFRED PIT only 2014+; VXV 2007-14 exploratory | no | BIL excess +5.69%, p=.035 | FAILED: DD >15% | No; frozen |
| G 20/80 QQQ/BIL | #455 | `7c80dc7` | **PASSIVE_RISK_BUDGET_BASELINE** | CAGR 4.42%, MaxDD -11.38%, vol 4.32% | calibrated `historical_backtest`, 5 bps | daily prices; no macro PIT | none | BIL excess +3.17%, p=.0003 | NOT alpha; passive baseline | Paper tracking only; no weight search |
| QQQ Transition | #438/#455 | `9b6effa` / `7c80dc7` | **NO_EXTRA_STRATEGY_VALUE / NO-GO** | PR438 adj CAGR 1.86%, vol 2.266%, MaxDD -6.37% | 10 bps all-legs | adjusted NAV; raw/cash rebuild vol 2.816% | no | risk-matched passive CAGR 2.95% | Transition does not beat passive at same vol | No further parameter research |
| Qlib-inspired composite | #404 | `0c8be9c` | NO-GO | test 2023+ excess +4.37%/yr at 5 bps; MaxDD -13.61% | 5/10/20 bps | current-universe, survivorship; not PIT | no true OOS | 2018-22 excess -3.82% | Rejected: regime-dependent | PIT universe + delisted prices |
| Qlib Ridge baseline | #389 | 22f8a1c | NO-GO | 9 rebalances: net ann 39.85%, Sharpe 2.78, MaxDD -2.72% | 5/10/20 bps one-way | 2-year PIT panel, 498 tickers; current-universe composition | only 9 test months, not stable OOS | benchmark alpha t=1.95, 95% CI includes 0 | FAILED: insufficient independent observations | More non-overlapping test months + PIT universe; no re-tune |
| Five-factor validation | #392 / #387 | `b8a41fe` / `0ef8bde` | NO-GO | test 2023+ no BH q<.05; benchmark CAGR 14.31% | 5 bps one-way | current universe, survivorship | chronological only | no corrected significance | FAILED | PIT universe; new prereg |
| Formula factor screen | #348 | `93a4257` | NO-GO | best ATR 20D Q5-Q1 2.60% gross; FDR q=.066 | 5 bp/leg approximation | 2-year panel; overlap | no | no FDR q<.05 | FAILED | New independent data and untouched holdout |
| PIT macro/event audit | #421/#390/#393 | `cb40f3a`/`fb39cff`/`e334dcc` | DATA_BLOCKED | audit only | n/a | ALFRED key absent; 97/98 failed tickers not delisting-verified; 91.61% coverage | no | n/a | INSUFFICIENT_DATA | Paid/verified delisted OHLCV + release timestamps |
| Qlib/OpenBB readiness | #389 | `22f8a1c` | DATA_BLOCKED | 502-instrument export, 18 features | n/a | Qlib not installed; OpenBB not independently validated; current universe | no | n/a | NOT READY | Reproducible Qlib install + independent provider audit |

---

## 3. Cost-model decision-sensitivity review

Cost-only deltas from the calibrated model:

| Case | Old cost | New cost | Delta | Decision margin |
|---|---:|---:|---:|---|
| A | $4,621.04 | $4,618.78 | -$2.26 | DD -25.59%, 10.59pp over limit |
| B | $5,726.25 | $5,728.58 | +$2.32 | DD -15.20%, 0.20pp over limit |
| C | $1,034.94 | $1,034.48 | -$0.46 | fails statistical/return gate |
| D | $1,141.32 | $1,138.51 | -$2.80 | DD -24.24%, 9.24pp over |
| E | $3,872.06 | $3,864.15 | -$7.91 | DD -32.18%, 17.18pp over |
| F | $1,497.84 | $1,494.88 | -$2.96 | DD -25.83%, 10.83pp over |

Largest delta **-$7.91**, 0.016% of $50,000 total over the full sample. It cannot
change any MaxDD gate; no strategy is within $8 of the 15% threshold in a way
that cost could flip. **No full NAV/HAC/Bootstrap rerun is justified for A-F.**
Their reports keep the old cost layer and are annotated accordingly. G and the
Transition passive control use the calibrated model.

F remains NO-GO; the cost audit does not promote it.

---

## 4. Data and research-design readiness

### PIT coverage

- Macro: ALFRED coverage is series-specific; NFCI/T10Y3M PIT was not fully
  verified before 2014; DFII10 has 2007+ vintages.
- Event/macro PIT audit lacks FRED/ALFRED API keys; current CSV is not a vintage.
- `BAMLH0A0HYM2` current history is only ~3 years and was rejected as a long
  credit series.

### Historical universe / delisting

- Current-universe panels are survivorship-biased.
- 98 download failures: 97 are not in the current SEC map; delisting/merger is
  plausible but not filing-verified.
- Free Stooq endpoint returned a JS challenge, not data.
- SEC company tickers provide identity, not historical OHLCV.

### Corporate actions

- ETF studies use provider-adjusted prices plus explicit cash-dividend
  bookkeeping; split adjustment is provider-dependent.
- The Transition adjusted vs raw/cash discrepancy is a live example: same orders
  can produce 2.266% vs 2.816% vol under different total-return conventions.

### Qlib

- Qlib not installed; no Qlib model/backtest was actually validated.
- Rolling retraining stability is unproven because no rolling retrain was run on
  a PIT universe.
- The Qlib-compatible export is an input, not validation.

### Independent sample

- Every strategy above has been studied on overlapping 2007-2026 or 2016-2026
  data.
- No candidate has a genuinely untouched forward sample.
- Forward paper data has not accumulated enough independent observations.

---

## 5. Project readiness

**The project is not ready to resume alpha-oriented factor research.**

Reasons:

1. No delisting-inclusive historical OHLCV universe.
2. Macro PIT release timestamps are incomplete.
3. Corporate-action conventions are not uniform across providers.
4. No independent untouched holdout.
5. Qlib rolling-retrain stability has not been demonstrated.

It **is ready** to maintain:

- G as a passive risk-budget baseline;
- accounting/cost audits;
- forward paper observation with no promotion claims.

---

## 6. Next research direction (one only)

**Build a verified historical universe and delisted-security OHLCV dataset
before any new factor.**

Minimum acceptance:

- point-in-time index membership by date;
- delisted/acquired tickers with final prices;
- split/dividend-adjusted and raw fields from one provider;
- reproducible vendor manifest + SHA-256;
- at least 10 years, with a 3-year untouched holdout;
- release timestamps for any macro/event feature.

Until then, do not launch another factor search. Free-source trials already
failed (Stooq challenge, yfinance delisting gaps, OpenBB unverified).

---

## 7. Frozen decisions

- A/B/C: NO-GO; no parameter rescue.
- D: NO-GO; PIT_UNVERIFIED.
- E: NO-GO; DD -32.18%.
- F: NO-GO; DD -25.83%.
- Transition: **NO_EXTRA_STRATEGY_VALUE / NO-GO**; frozen.
- G: **PASSIVE_RISK_BUDGET_BASELINE**; not alpha.
- Qlib, five-factor, formula: NO-GO.
- PIT / Qlib-OpenBB: DATA_BLOCKED.

No new PR is created for this register; it is added to PR #455.
