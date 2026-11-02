# Short-Term Relative-Reversal Screen — Results

Date: 2026-11-02  
Status: **NEGATIVE / EXPLORATORY ONLY**  
Implementation PR: [#429](https://github.com/wijouyang-lab/us/pull/429)  
Pre-registration protocol: [#428](https://github.com/wijouyang-lab/us/pull/428)

## 1. Reproducibility

- Stock screen workflow: [run 41402161569](https://github.com/wijouyang-lab/us/actions/runs/41402161569) — success.
- Full repository test workflow: [run 41402161597](https://github.com/wijouyang-lab/us/actions/runs/41402161597) — **1,346 passed, 1 skipped, 42 warnings**.
- Inputs: `research_price_history_sp500_10y.csv` (89,541,522 bytes; SHA-256 `2f9a31429ff2d3947dcd388d75c4d18cb1cc82346946b9a92f48f3a98748b355`) and `research_spy_sp500_10y.csv` (197,643 bytes; SHA-256 `86d0fe36381b20409846d5ef230b3243f8e42ec7dd4ccfb860f8bc5c884ea0cb`).
- Stock panel: 1,233,984 rows across 503 tickers; SPY calendar: 2,532 sessions, 2016-09-19 to 2026-10-14.
- 2,202 usable signal dates from 2018-01-02; latest event date 2026-10-06.
- Missing selected-name execution events: 2. Missing universe execution-name observations: 6. Missing SPY execution events: 0.

## 2. Fixed experiment

- Rank eligible stocks by 5-session stock price return minus 5-session SPY price return.
- Long the bottom 20% (weakest relative performers); close >= $5, 20-session average dollar volume >= $5m, at least 80 eligible names.
- Signal after close; entry at next exact SPY session Open; exit at Open after 1, 3, or 5 further SPY sessions.
- Primary horizon: 3 sessions. Regimes use SPY Close relative to MA200 and the 20-session MA200 slope.
- Compare with the same-day equal-weight eligible stock universe and SPY.
- Costs: 5/10/20/50 bps per side, deducted as a simple full-notional round trip.
- Overlapping daily event returns use Newey-West/HAC lag H-1. BH adjustment covers nine 2024+ horizon/regime tests at 10 bps per side.
- This is an event study. Do not interpret its means as portfolio CAGR or its event observations as independent daily NAV returns.

## 3. Primary horizon (3 sessions), 10 bps per side

All return figures are percent per event. Excess is relative to the same-date eligible equal-weight stock benchmark.

| Period | Regime | Events | Non-overlap events | Net mean | Mean excess | Median excess | HAC t | HAC 95% CI for mean excess |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 2018–2020 | RISK_ON | 587 | 199 | -0.062 | -0.169 | -0.192 | -3.60 | [-0.262, -0.077] |
| 2018–2020 | RISK_OFF | 102 | 36 | +1.774 | +0.684 | +0.240 | +2.17 | [+0.066, +1.301] |
| 2018–2020 | TRANSITION | 63 | 29 | -0.769 | -0.306 | -0.149 | -0.49 | [-1.541, +0.928] |
| 2021–2023 | RISK_ON | 460 | 157 | -0.015 | -0.189 | -0.199 | -3.55 | [-0.293, -0.084] |
| 2021–2023 | RISK_OFF | 180 | 62 | +0.128 | -0.072 | -0.186 | -0.68 | [-0.281, +0.137] |
| 2021–2023 | TRANSITION | 109 | 39 | -0.044 | -0.008 | -0.032 | -0.06 | [-0.281, +0.265] |
| 2024–2026-10-06 | RISK_ON | 635 | 213 | +0.070 | -0.099 | -0.112 | -1.96 | [-0.197, -0.0002] |
| 2024–2026-10-06 | RISK_OFF | 15 | 5 | +1.552 | -0.195 | -0.254 | -0.62 | [-0.811, +0.420] |
| 2024–2026-10-06 | TRANSITION | 42 | 16 | +0.053 | -0.038 | -0.128 | -0.11 | [-0.712, +0.635] |

2024+ BH-adjusted q-values for mean excess vs equal weight:
- H1 RISK_ON: **1.04e-9**, with negative excess (the reversal selection significantly underperformed this benchmark in this sample).
- H3 RISK_ON: 0.223; H5 RISK_ON: 0.580.
- All RISK_OFF and TRANSITION cells: q >= 0.580.
- The 2024+ RISK_OFF sample has only 5 non-overlapping H3 events and 3 non-overlapping H5 events; it is not sufficient to support a bear-market reversal claim.

## 4. Robustness horizons

For 2024+ RISK_ON at 10 bps per side:
- H1: net mean -0.102%, mean excess -0.161%, median excess -0.172%, 636 events; HAC 95% CI [-0.210%, -0.112%], BH q=1.04e-9.
- H3: net mean +0.070%, mean excess -0.099%, median excess -0.112%, 635 events; HAC 95% CI [-0.197%, -0.0002%], BH q=0.223.
- H5: net mean +0.198%, mean excess -0.085%, median excess -0.123%, 635 events; HAC 95% CI [-0.229%, +0.059%], BH q=0.580.

The selected weak-relative-return names did not show a stable rebound. The one strong result is in the wrong direction: one-day reversal selection underperformed the equal-weight universe.

## 5. Cost sensitivity — primary H3, 2024+

| Regime | bps/side | Net mean | Net excess vs equal weight |
|---|---:|---:|---:|
| RISK_ON | 5 | +0.170 | +0.001 |
| RISK_ON | 10 | +0.070 | -0.099 |
| RISK_ON | 20 | -0.130 | -0.299 |
| RISK_ON | 50 | -0.730 | -0.899 |
| RISK_OFF | 5 | +1.652 | -0.095 |
| RISK_OFF | 10 | +1.552 | -0.195 |
| RISK_OFF | 20 | +1.352 | -0.395 |
| RISK_OFF | 50 | +0.752 | -0.995 |
| TRANSITION | 5 | +0.153 | +0.062 |
| TRANSITION | 10 | +0.053 | -0.038 |
| TRANSITION | 20 | -0.147 | -0.238 |
| TRANSITION | 50 | -0.747 | -0.838 |

Even the 5 bps/side RISK_ON case is effectively equal to the equal-weight benchmark (+0.001% mean excess per event), before market impact and fill-level slippage.

## 6. Decision

**The pre-registered short-term stock relative-reversal screen does not pass.**

- In RISK_ON, the selected laggards consistently underperformed the equal-weight stock benchmark across development, validation, and later periods.
- The isolated 2018–2020 RISK_OFF positive mean excess did not repeat in 2021–2023; 2024+ RISK_OFF has only 5/3 non-overlapping observations for H3/H5 and cannot be interpreted as proof.
- No tested horizon/regime offers stable, cost-resilient positive excess after considering the predeclared multiple-testing family.
- Do not tune the same 5-day ranking threshold, regime boundaries, or holding horizon against this reused panel. Preserve this as a negative result.
- Do not add this signal to Strategy Lab, the adaptive allocator, the Trend V1 portfolio, or production.

## 7. Limitations and next valid question

- The 503-name price download is based on the **current** Wikipedia S&P 500 list. Historical membership filtering cannot recover prices for removed/delisted firms absent from the source input. Survivorship bias remains.
- Price returns exclude dividends. Costs are simplified event-level round-trip deductions, not fill-level spread, market-impact, capacity, or rejected-order simulation.
- The 2024+ period was already used in exploratory research; it is not an untouched holdout.
- Regime classification is based only on SPY data available at each signal close, but uses a simple MA200 definition.
- The four Trend V1 ETFs (GLD, IWM, QQQ, TLT) still lack repository-tracked reproducible history. ETF mean-reversion research is data-blocked and must remain separate from stock cross-sectional tests.

A future research direction would require a genuinely different pre-registered hypothesis (for example, event-driven liquidity/volatility shock reversal) and preferably a broader survivorship-aware universe. Do not rename or lightly retune this failed 5-day relative-laggard signal.
