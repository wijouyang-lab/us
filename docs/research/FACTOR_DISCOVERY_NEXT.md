# Next Factor Discovery Plan (Research Only)

**Status:** experiment plan; no new factor is approved or claimed profitable.
**Scope:** research branch only. Do not change production scoring, scanner, premarket trigger, portfolio, or orders.

## Why this stage is necessary

- The historical technical-factor report identifies ATR_Pct as the strongest candidate, but it still needs independent reproduction with frozen definitions, cost-aware portfolio construction, and a clean out-of-sample period.
- The BP report has only three walk-forward windows and explicitly labels the result unstable.
- The existing multi-factor quantile report chooses factor directions from in-sample IC and uses overlapping forward returns; those results are exploratory, not validation.
- The current event-factor archive has no reviewed labels and cannot validate event alpha.
- The experiment summary should be audited before reuse: multiple factors share identical summary return statistics, which may indicate an upstream join, grouping, or artifact freshness defect.

## Candidate families to test

Run each candidate as a separate, predeclared experiment. Do not pick the sign from the full sample.

| Priority | Candidate | Definition to freeze | Main risk / control |
|---|---|---|---|
| P0 | ATR_Pct / realized volatility | ATR divided by price; 20-session realized volatility as a separate comparator | May proxy market/sector risk; sector and beta neutralization |
| P1 | Short-term reversal | Prior 1–5 session return, with overnight/intraday variants only if timestamped data exists | Bid-ask bounce, microcaps, stale prices; liquidity floor and costs |
| P1 | Medium-term momentum excluding recent month | 12–1 month return; compare with existing 20D/60D momentum | Choose direction on training data only; test regime/universe dependence |
| P1 | Quality | ROE and available profitability measures, evaluated individually before composites | Accounting release lags, stale filings, financial-sector comparability |
| P1 | Value | EP_TTM and BP separately, with industry-relative ranks | PIT reporting dates, negative earnings, sector effects, value traps |
| P2 | Quality × value | Frozen interaction/rank combination | Avoid optimizing weights on test data; compare to each component |
| P2 | Gap / overnight reversal | Open-to-prior-close gap and next-session response, only with trustworthy OHLC data | Corporate actions, earnings gaps, adjusted-price integrity |
| P2 | Volatility-regime interaction | Candidate factor × lagged market-volatility regime | Regime labels must be lagged and use no future information |
| P2 | Earnings/news surprise | Actual versus consensus and timestamped event response, only with validated coverage | Current event labels and SEC coverage are insufficient; no synthetic labels |
| P2 | Macro-event sensitivity | Predeclared response around Fed/BEA/BLS/Treasury releases | Historical vintages, consensus and first-seen timestamps required |

## Required evaluation protocol

1. Audit the research panel first: unique date/ticker keys, merge cardinality, factor variation, forward-return construction, corporate-action adjustment, and whether each factor summary comes from its own ranked buckets. Fail fast if unrelated factors have identical unexplained outputs.
2. Freeze definitions and signs. Direction may be selected on training data only. Document transformations, winsorization, sector neutralization, missing-value handling, and rebalance timing before testing.
3. Use chronological splits with horizon purging. Keep train, validation and final test ordered by date. Purge at least the forward-return horizon at boundaries. Use non-overlapping return windows as a separate inference check.
4. Use comparable universes. Compare each factor and the price-only baseline on the same point-in-time universe and dates. Do not treat current S&P 500 constituents as the historical universe.
5. Evaluate economics, not only IC: rank IC/ICIR, Q5–Q1 spread, monotonicity, turnover, gross/net returns, realistic spread/slippage costs, Sharpe, drawdown, beta/sector exposures and confidence intervals.
6. Correct for multiple testing. Record every tested candidate, including failures; use a predeclared list and multiple-testing-aware robustness checks. Do not report only the winner.
7. Require repeatability. Keep a candidate research-only unless it is directionally stable across walk-forward windows, survives costs and reasonable parameter perturbations, and beats the same-date price-only baseline on the frozen final test.

## Decision labels

- BLOCKED_DATA: panel, timestamp, or provenance defect.
- NO_SIGNAL: no meaningful out-of-sample rank or portfolio spread.
- FRAGILE: positive result that fails stability, cost, or robustness checks.
- CANDIDATE_FOR_REPLICATION: passes initial frozen tests but needs independent replication.
- REPLICATED_RESEARCH_SIGNAL: repeated out-of-sample evidence; still not automatic production approval.

## Immediate execution order

1. Audit the experiment summary/join path and fix any factor-to-return alignment defect.
2. Re-run ATR_Pct and realized volatility as locked comparators, with non-overlapping and net-of-cost portfolio tests.
3. Test short-term reversal and 12–1 momentum on the same price panel.
4. Test EP_TTM, BP and ROE using genuine point-in-time accounting availability.
5. Revisit news/earnings/macro factors only after event timestamp and label gates pass.

A passing unit test proves the code behaves as specified; it does not prove that a factor predicts returns. No result in this plan authorizes live trading.