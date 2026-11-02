# Volume-Shock Reversal Study

Date: 2026-11-03
Status: **FAILED (research only; no deployable alpha)**
Branch: `research/volume-shock-reversal`

## 1. Hypothesis

A liquid ETF that falls by an extreme amount on abnormal dollar volume may
mean-revert over the next few sessions. The test is deliberately narrow and was
fixed before looking at results.

This is **not** a continuation of QQQ TRANSITION five-day reversal, momentum,
trend, ATR/volatility, or the cross-sectional short-reversal work.

## 2. Locked specification

Universe:

```text
QQQ, IWM, GLD, TLT
SPY = market benchmark only
BIL = cash/reserve, not a reversal candidate
```

For each ETF:

```text
r(t)          = ln(AdjClose(t) / AdjClose(t-1))
sigma20(t)    = StdDev(r(t-20) ... r(t-1))
Z(t)          = r(t) / sigma20(t)
DollarVolume  = Close(t) * Volume(t)
MedianDV20(t) = Median(DV(t-20) ... DV(t-1))
DV_Ratio(t)   = DV(t) / MedianDV20(t)
```

Event only when:

```text
Z(t) <= -2.5
DV_Ratio(t) >= 2.0
```

Both thresholds and the 20-session lookback were fixed before running. No
parameter variants were tested or selected.

Execution:

- signal after close N;
- entry next XNYS Open;
- exit Open after 3 further XNYS sessions for the primary test;
- 1 and 5 sessions are secondary only;
- no overlapping position per ETF and no overlapping global portfolio position;
- missing expected entry/exit price fails closed;
- no historical backfill.

## 3. Data and bias disclosure

Source: yfinance, free, no token. Coverage and SHA-256 are in
`data/research/volume_shock_reversal/manifest.json`.

| Ticker | Start | End | Rows |
|---|---:|---:|---:|
| QQQ | 2006-01-03 | 2026-11-02 | 5,241 |
| IWM | 2006-01-03 | 2026-11-02 | 5,241 |
| GLD | 2006-01-03 | 2026-11-02 | 5,241 |
| TLT | 2006-01-03 | 2026-11-02 | 5,241 |
| SPY | 2006-01-03 | 2026-11-02 | 5,241 |
| BIL | 2007-05-30 | 2026-11-02 | 4,889 |

Study window: **2007-05-30 to 2026-11-02**.

Checks performed:

- OHLCV present; Volume finite and positive;
- AdjClose finite and positive;
- duplicate dates rejected;
- no missing session inside the study window;
- no interpolation or forward fill;
- per-file SHA-256 recorded;
- source and retrieval time recorded.

Bias:

- Provider-adjusted prices are used, not point-in-time raw exchange records.
- The four ETFs are today's surviving, liquid instruments. Selection after the
  fact is a survivorship and selection bias.
- No delisted ETF universe is included.
- No individual-stock PIT data is used; the known 91.61% PIT coverage problem is
  not being papered over.

## 4. Event study

Method:

- Newey-West HAC regression of forward ETF return on event dummy, fixed
  **20-session lag**;
- 4 ETFs x 3 horizons = 12 tests;
- Benjamini-Hochberg across all 12;
- return measured next Open to Open after h sessions;
- excess return measured against SPY over the same calendar window;
- event count and non-overlapping count disclosed separately;
- cost shown for four actual legs.

### Event results

| ETF | H | Events | Non-overlap | Mean | Excess SPY | HAC p | BH q | Net @10bps |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| QQQ | 1 | 47 | 44 | +0.38% | +0.21% | 0.215 | 0.646 | -0.02% |
| QQQ | 3 | 47 | 41 | **+1.02%** | **+0.45%** | **0.034** | **0.363** | **+0.62%** |
| QQQ | 5 | 47 | 37 | +1.13% | +0.44% | 0.080 | 0.363 | +0.73% |
| IWM | 1 | 23 | 23 | -0.46% | -0.41% | 0.091 | 0.363 | -0.86% |
| IWM | 3 | 23 | 21 | -0.40% | -0.46% | 0.281 | 0.675 | -0.80% |
| IWM | 5 | 23 | 21 | -0.27% | -0.47% | 0.355 | 0.710 | -0.67% |
| GLD | 1 | 52 | 50 | +0.10% | -0.27% | 0.787 | 0.859 | -0.30% |
| GLD | 3 | 52 | 47 | +0.20% | -0.25% | 0.749 | 0.859 | -0.20% |
| GLD | 5 | 52 | 45 | +0.40% | -0.03% | 0.581 | 0.830 | -0.00% |
| TLT | 1 | 31 | 31 | +0.09% | +0.55% | 0.623 | 0.830 | -0.31% |
| TLT | 3 | 31 | 29 | +0.02% | +0.55% | 0.919 | 0.919 | -0.38% |
| TLT | 5 | 31 | 29 | +0.34% | +0.80% | 0.522 | 0.830 | -0.06% |

3D HAC 95% CIs: QQQ +0.06% to +1.60% (median +0.80%, std 3.46%); IWM -1.48% to +0.43%; GLD -0.39% to +0.54%; TLT -0.52% to +0.47%. The QQQ interval excludes zero only marginally and overlaps economically small effects.\n\n**No ETF/horizon has BH q < 0.05.** QQQ 3D has a raw p of 0.034, but it does
not survive multiple testing (q = 0.363). IWM is outright negative. GLD and TLT
are statistically indistinguishable from zero.

QQQ 3D has 41 non-overlapping events, GLD 47; IWM (21) and TLT (29) fail the
30-independent-event minimum. Even QQQ's positive raw result is not evidence of
a deployable effect.

## 5. Daily NAV portfolio

Rules:

- $50,000 initial;
- 25% strategy sleeve, 75% BIL reserve;
- long only, no leverage;
- one position maximum;
- signal date N, entry N+1 Open, exit N+4 Open (3 further sessions);
- if multiple ETFs signal on the same date, choose the lowest Z; tie by ticker;
- new signals while held are skipped;
- four actual legs with costs per leg.

### Portfolio results

| Cost/leg | Final NAV | CAGR | Vol | Sharpe | MaxDD | Trades | Win | Avg trade | Total cost |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 bps | $62,817.53 | 1.18% | 1.58% | 0.74 | -5.89% | 113 | 47.8% | -0.11% | $2,649.98 |
| 10 bps | $60,055.49 | **0.95%** | 1.46% | 0.65 | **-6.44%** | 113 | 46.0% | -0.31% | $4,754.49 |
| 20 bps | $56,094.51 | 0.59% | 1.27% | 0.46 | -8.80% | 113 | 34.5% | -0.71% | $7,751.66 |
| 50 bps | $50,949.23 | 0.10% | 1.00% | 0.08 | -14.50% | 113 | 15.9% | -1.90% | $11,565.47 |

Exposure: 7.0% of sessions; turnover at 10 bps: 95.1x initial capital.

### Benchmarks

| Benchmark | Final NAV | CAGR | Vol | Sharpe | MaxDD |
|---|---:|---:|---:|---:|---:|
| 100% BIL | $65,536.51 | 1.39% | 0.49% | 2.81 | -0.78% |
| 25% SPY + 75% BIL | $107,052.87 | **4.00%** | 4.88% | 0.83 | -14.91% |
| 25% QQQ + 75% BIL | $136,439.17 | **5.31%** | 5.56% | 0.96 | -14.68% |
| 100% SPY | $351,505.29 | 10.56% | 19.66% | 0.61 | -55.19% |
| 100% QQQ | $854,445.04 | 15.74% | 22.33% | 0.77 | -53.40% |

At 10 bps the strategy's CAGR is **0.95%**, below even 100% BIL (1.39%) and far
below both risk-matched benchmarks: SPY25 (4.00%) and QQQ25 (5.31%).

## 6. Stability by period (10 bps)

| Period | CAGR | Vol | Sharpe | MaxDD |
|---|---:|---:|---:|---:|
| 2007-2015 | **-0.31%** | 1.59% | -0.19 | -6.44% |
| 2016-2020 | +0.50% | 1.37% | 0.37 | -2.94% |
| 2021-latest | +3.23% | 1.32% | 2.37 | -1.49% |

The result is not stable. It is negative in the first eight-plus years and only
turns positive recently. This is exactly the pattern that should not be promoted.

## 7. Required questions

1. **Does the event signal produce a rebound?**
   Only QQQ 3D shows a positive raw mean (+1.02%), but it does not survive BH
   correction and is not stable. No broad rebound effect.

2. **Which ETF has a statistical effect?**
   None at q < 0.05. QQQ has a raw 3D p=0.034; GLD/TLT are flat; IWM is negative.

3. **Does the effect survive real leg costs?**
   QQQ 3D remains +0.62% at 10 bps per event, but the daily portfolio does not:
   0.95% CAGR versus 4.00%/5.31% for risk-matched benchmarks. At 20/50 bps the
   portfolio is close to zero. No.

4. **Is the 3-day holding period effective?**
   QQQ 3D is the best raw point, but after BH it is insignificant. 1D/5D do not
   provide independent confirmation. Not effective as a validated result.

5. **Is every historical period stable?**
   No: 2007-2015 negative, 2016-2020 marginal, 2021-latest positive. The
   strategy depends on the recent period.

6. **Does full daily NAV beat risk-matched benchmarks?**
   No. 0.95% CAGR vs 4.00% SPY25 and 5.31% QQQ25 at 10 bps. At 5 bps it is still
   1.18% vs benchmarks above 4.00%.

7. **Is max drawdown within 15%?**
   Yes: -6.44% at 10 bps; -14.50% at 50 bps. This is the only passing risk
   criterion, but it comes with near-zero return and low exposure.

8. **Final verdict?**
   **FAIL.** The event is not a validated rebound, does not survive multiple
   testing, does not beat risk-matched benchmarks, and is not stable across
   periods.

## 8. Acceptance checklist

| Requirement | Result |
|---|---|
| Enough independent main events for all ETFs | No: IWM 21, TLT 29 |
| 3D BH q < 0.05 | No: best q 0.363 |
| Positive net return at 10 bps | Yes, but only +0.95% CAGR |
| Beats 25% SPY + 75% BIL | No |
| Beats 25% QQQ + 75% BIL | No |
| Max DD <= 15% | Yes (-6.44%) |
| Not dependent on one trade/period | No: 2007-2015 negative |
| Three fixed interval reports | Yes, all reported; not all positive |

Verdict: **FAIL**, not PASS and not a deployable candidate.

## 9. Engineering and isolation

- Code: `tools/research/volume_shock_reversal.py`
- Plot helper: `tools/research/plot_volume_shock.py`
- Tests: `tests/test_volume_shock_reversal.py`
- Data: `data/research/volume_shock_reversal/`
- Results: `docs/research/volume_shock_reversal/`
- No production Scan/Scoring/ATR/Stop changes.
- No Portfolio-50000 or generic paper-ledger changes.
- No IBKR connection or orders.
- PR #441 remains Draft/Open; its prospective account remains NOT_STARTED.

## 10. Artifacts

```text
docs/research/volume_shock_reversal/event_study.csv
docs/research/volume_shock_reversal/trades.csv
docs/research/volume_shock_reversal/nav_10bps.csv
docs/research/volume_shock_reversal/benchmark_nav.csv
docs/research/volume_shock_reversal/results.json
docs/research/volume_shock_reversal/nav_strategy.svg
docs/research/volume_shock_reversal/event_3d.svg
```

The SVG files are dependency-free charts generated from the committed CSVs.

