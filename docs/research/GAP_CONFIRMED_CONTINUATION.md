# Gap-Confirmed Continuation Study

Date: 2026-11-03  
Status: **FAILED (research only; no deployable alpha)**  
Branch: `research/gap-confirmed-continuation`

## 1. Hypothesis

An ETF that gaps up overnight and continues higher during the regular session
may signal confirmed price discovery, followed by 1/3/5-session continuation.

This is deliberately different from the failed short-reversal, momentum/trend,
ATR/volatility, QQQ five-day reversal, and volume-shock reversal studies. It does
not use volume conditioning.

## 2. Locked specification

Candidate ETFs:

```text
SPY, QQQ, IWM, GLD, TLT
BIL = cash/reserve only
```

Formulas:

```text
AdjustedOpen(t) = Open(t) * AdjClose(t) / Close(t)
Overnight(t)     = AdjustedOpen(t) / AdjClose(t-1) - 1
Intraday(t)      = AdjClose(t) / AdjustedOpen(t) - 1

SigmaOvernight(t) = StdDev(Overnight(t-20) ... Overnight(t-1))
SigmaIntraday(t)  = StdDev(Intraday(t-20) ... Intraday(t-1))
OvernightZ(t)     = Overnight(t) / SigmaOvernight(t)
IntradayZ(t)      = Intraday(t) / SigmaIntraday(t)
```

Fixed signal:

```text
OvernightZ >= +1.0
AND
IntradayZ >= +0.5
```

Signal is known only after the close. No threshold variants were tested.

Execution:

- entry next XNYS Open;
- primary hold: 3 further XNYS sessions;
- exit Open of the third further session;
- 1 and 5 sessions are secondary but included in all tests;
- no overlapping position per ETF or globally;
- missing entry/exit price fails closed;
- no delayed historical backfill.

## 3. Data

Reused `data/research/volume_shock_reversal/`:

| Ticker | Start | End | Rows |
|---|---:|---:|---:|
| SPY | 2006-01-03 | 2026-11-02 | 5,241 |
| QQQ | 2006-01-03 | 2026-11-02 | 5,241 |
| IWM | 2006-01-03 | 2026-11-02 | 5,241 |
| GLD | 2006-01-03 | 2026-11-02 | 5,241 |
| TLT | 2006-01-03 | 2026-11-02 | 5,241 |
| BIL | 2007-05-30 | 2026-11-02 | 4,889 |

Study window: **2007-05-30 to 2026-10-30**. The 2026-11-02 bar is excluded
because it was incomplete at download time.

Checks:

- OHLCV and AdjClose present;
- Volume finite and positive;
- duplicate dates rejected;
- no missing session in the study window;
- no fill/interpolation;
- SHA-256 recorded in `manifest.json`.

Bias disclosure:

- yfinance provider-adjusted prices, not exchange PIT records;
- current surviving ETF sample only; survivorship and ex-post selection bias;
- no delisted ETF universe;
- no individual-stock PIT data.

## 4. Event study

5 ETFs × 3 horizons = **15 tests**. Newey-West HAC lag = 20 on the full daily
time axis. BH correction across all 15.

| ETF | H | Events | Non-overlap | Mean | Median | Excess SPY | HAC t | HAC 95% CI | p | q |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SPY | 1 | 300 | 291 | -0.03% | +0.10% | 0.00% | -1.18 | -0.21%..+0.05% | 0.240 | 0.449 |
| SPY | 3 | 300 | 263 | +0.06% | +0.31% | 0.00% | -0.72 | -0.32%..+0.15% | 0.470 | 0.542 |
| SPY | 5 | 300 | 239 | -0.00% | +0.31% | 0.00% | -1.56 | -0.57%..+0.06% | 0.118 | 0.344 |
| QQQ | 1 | 286 | 277 | -0.11% | +0.01% | -0.00% | -2.21 | -0.36%..-0.02% | 0.027 | 0.344 |
| QQQ | 3 | 286 | 262 | -0.06% | +0.20% | +0.01% | -1.94 | -0.56%..+0.00% | 0.052 | 0.344 |
| QQQ | 5 | 286 | 241 | +0.07% | +0.43% | +0.08% | -1.49 | -0.65%..+0.09% | 0.138 | 0.344 |
| IWM | 1 | 278 | 269 | -0.07% | -0.03% | -0.04% | -1.37 | -0.28%..+0.05% | 0.170 | 0.364 |
| IWM | 3 | 278 | 247 | +0.02% | +0.00% | -0.06% | -0.74 | -0.41%..+0.19% | 0.459 | 0.542 |
| IWM | 5 | 278 | 228 | +0.02% | +0.23% | -0.11% | -1.02 | -0.58%..+0.18% | 0.310 | 0.517 |
| GLD | 1 | 233 | 221 | +0.00% | +0.02% | -0.08% | -0.50 | -0.19%..+0.12% | 0.617 | 0.661 |
| GLD | 3 | 233 | 204 | +0.11% | +0.09% | -0.10% | -0.13 | -0.28%..+0.25% | 0.898 | 0.898 |
| GLD | 5 | 233 | 186 | +0.06% | +0.11% | -0.07% | -0.85 | -0.51%..+0.20% | 0.395 | 0.539 |
| TLT | 1 | 264 | 252 | -0.08% | -0.04% | -0.11% | -1.58 | -0.23%..+0.02% | 0.114 | 0.344 |
| TLT | 3 | 264 | 231 | -0.14% | +0.01% | -0.44% | -1.73 | -0.42%..+0.03% | 0.083 | 0.344 |
| TLT | 5 | 264 | 206 | -0.04% | -0.01% | -0.42% | -0.89 | -0.39%..+0.15% | 0.375 | 0.539 |

No positive q < 0.05 result. The only raw p < 0.05 is QQQ 1D, and it is
**negative** (-0.11% mean); after BH it is q = 0.344.

Event returns are net of four legs at 10 bps in `mean_net_10bps`; all are
negative or essentially zero.

## 5. Daily NAV portfolio

Rules:

- $50,000 initial;
- 25% strategy sleeve;
- 75% BIL;
- long only, one position;
- same-day tie-break: highest `OvernightZ + IntradayZ`, then ticker;
- 3-session primary exit;
- four actual legs with per-leg costs.

### Portfolio results

| Cost/leg | Final NAV | CAGR | Vol | Sharpe | MaxDD | Trades | Win | Avg trade | Cost | Turnover | Exposure |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 bps | $54,327.81 | 0.43% | 2.10% | 0.21 | -14.79% | 586 | 49.0% | -0.16% | $9,643.15 | 385.7x | 36.0% |
| **10 bps** | **$50,762.86** | **0.08%** | 1.66% | 0.06 | **-18.42%** | 586 | 44.0% | -0.36% | $12,381.98 | 247.6x | 36.0% |
| 20 bps | $49,316.60 | -0.07% | 1.32% | -0.05 | -20.70% | 586 | 31.4% | -0.76% | $13,367.42 | 133.7x | 36.0% |
| 50 bps | $49,163.25 | -0.09% | 0.98% | -0.09 | -21.99% | 586 | 11.8% | -1.94% | $13,552.82 | 54.2x | 36.0% |

At the primary 10 bps assumption the strategy is barely positive (0.08% CAGR)
but has **-18.42% max drawdown**, failing the 15% limit.

### Benchmarks

| Benchmark | Final NAV | CAGR | Vol | Sharpe | MaxDD |
|---|---:|---:|---:|---:|---:|
| 100% BIL | $65,536.51 | 1.40% | 0.49% | 2.87 | -0.78% |
| 25% SPY + 75% BIL | $107,052.87 | **4.00%** | 4.88% | 0.83 | -14.91% |
| 25% QQQ + 75% BIL | $136,439.17 | **5.31%** | 5.56% | 0.96 | -14.68% |
| 100% SPY | $351,505.29 | 10.56% | 19.66% | 0.61 | -55.19% |
| 100% QQQ | $854,445.04 | 15.74% | 22.33% | 0.77 | -53.40% |

The strategy loses to cash and to both risk-matched benchmarks.

## 6. Stability

10 bps:

| Period | CAGR | Vol | Sharpe | MaxDD |
|---|---:|---:|---:|---:|
| 2007-2015 | **-1.65%** | 2.34% | -0.70 | -16.9% |
| 2016-2020 | +0.32% | 0.84% | 0.38 | -1.7% |
| 2021-2026-10 | +2.50% | 0.67% | 3.70 | -1.2% |

The first period is negative and breaches the 15% drawdown limit. The recent
positive period cannot carry the result.

## 7. Diagnostics

Signal counts:

```text
SPY 300, QQQ 286, IWM 278, GLD 233, TLT 264
```

Regime counts: above 200D 1,019; below 200D 274; warm-up 68.  
Consecutive signals within 3 sessions: 169.  
Skipped signals while held/pending: 507.

Per-ETF PnL at 10 bps:

```text
QQQ +$1,199.50
SPY -$3,944.69
TLT -$5,004.56
IWM -$2,527.09
GLD -$1,225.86
```

Only QQQ contributes positively; four of five ETFs lose. Max single trade PnL
is $445.58 and the top three sum to $1,210.34. Final NAV excluding the top three
is **$49,552.53**, below the $50,000 initial capital.

Z-score distributions are in `results.json`; tails are approximately symmetric,
and the signal is not a rare extreme tail event after the 1.0/0.5 thresholds.

## 8. Required questions

1. **Does a gap plus intraday confirmation predict continuation?**  
   No. Mean 3-session returns are indistinguishable from zero or negative; no
   positive BH-significant result.

2. **Which ETF is statistically significant?**  
   None positive. QQQ 1D is raw-negative p=0.027; no positive test.

3. **Does BH correction preserve significance?**  
   No. Best q is 0.344; all 15 tests fail q<0.05.

4. **Is it profitable after all four legs?**  
   Barely at 10 bps (0.08% CAGR), negative at 20/50 bps, and below cash. No.

5. **Does it beat risk-matched benchmarks?**  
   No. 0.08% vs 4.00% SPY25 and 5.31% QQQ25.

6. **Are the three periods stable?**  
   No. 2007-2015 is -1.65% with -16.9% drawdown.

7. **Is max drawdown below 15%?**  
   No. -18.42% at 10 bps; worse at higher costs.

8. **Final verdict?**  
   **FAIL.**

## 9. Acceptance checklist

| Requirement | Result |
|---|---|
| Enough independent main events | Yes for all 5 |
| 3D BH q < 0.05 | No |
| Positive net CAGR at 10 bps | Yes, barely 0.08% |
| Beats 25% SPY + 75% BIL | No |
| Beats 25% QQQ + 75% BIL | No |
| MaxDD <= 15% | No, -18.42% |
| No systematic period failure | No, 2007-2015 negative |
| Not dependent on top 3 trades | No, ex-top3 NAV < $50,000 |

## 10. Engineering and isolation

- Code: `tools/research/gap_confirmed_continuation.py`
- Chart helper: `tools/research/plot_gap_confirmed.py`
- Tests: `tests/test_gap_confirmed_continuation.py`
- Results: `docs/research/gap_confirmed_continuation/`
- No production Scan/Scoring/ATR/Stop changes.
- No Portfolio-50000 or generic paper-ledger changes.
- No IBKR connection or orders.
- PR #441 remains Draft/Open and prospective remains NOT_STARTED.
- PR #443 is not merged; this branch only reuses its committed market data.

## 11. Artifacts

```text
docs/research/gap_confirmed_continuation/event_study.csv
docs/research/gap_confirmed_continuation/trades.csv
docs/research/gap_confirmed_continuation/nav_10bps.csv
docs/research/gap_confirmed_continuation/benchmark_nav.csv
docs/research/gap_confirmed_continuation/results.json
docs/research/gap_confirmed_continuation/nav_strategy.svg
docs/research/gap_confirmed_continuation/event_3d.svg
```
