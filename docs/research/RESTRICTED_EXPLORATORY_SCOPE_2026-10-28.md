# Restricted Exploratory Research Scope

Date: 2026-10-28
Research only. No production changes.

## Why this scope exists

The full-history PIT dataset gate remains blocked:

- member-session coverage 91.61% < 95%
- ticker coverage 84.23% < 98%
- 0/98 missing tickers have verified OHLCV
- no independent OHLCV source
- no corporate-action/PIT completion

The following restricted scope is the only currently defensible exploratory
track. It must not be described as full-history PIT or deployable alpha.

## Permitted scope

| Item | Restriction |
|---|---|
| Universe | 466 fully-priced tickers from the existing current-universe 10-year panel |
| History | 2016-09-19 to 2026-10-14; 2,532 sessions per included ticker |
| Price source | existing Yahoo-derived panel only |
| Survivorship | acknowledged; current-universe only |
| Delisted companies | excluded; not imputed or replaced |
| PIT claims | **forbidden** |
| Production claims | **forbidden** |
| Model output | exploratory only; no deployment |

The 2-year PIT snapshot (502 tickers, 462 sessions, 2024-12-09 to 2026-10-13)
may be used for method development where its own timestamp checks hold, but it
is still a short-window sample and does not establish 10-year PIT coverage.

## Required labels on any result

Every chart, table, or summary from this scope must carry:

```text
CURRENT-UNIVERSE EXPLORATORY 鈥?SURVIVORSHIP-BIASED
NOT A FULL PIT RESULT
NOT DEPLOYABLE ALPHA
```

## Prohibited interpretations

- Do not call the 503-ticker panel a historical S&P 500 universe.
- Do not compare its returns with a PIT benchmark as if unbiased.
- Do not fill delisted prices or drop difficult names to improve coverage.
- Do not use a strong current-universe backtest to justify production changes.
- Do not add production scanner, scoring, stop, ledger, or order-path changes.

## Gate

The full-history PIT gate remains authoritative for any PIT claim. The current
gate result is in:

`docs/research/pit_gate_current_result_2026-10-28.json`

Current result: data, strategy, and production stages all false.

## Permitted questions

- Does a feature implementation behave correctly?
- Is a signal stable under time splits within the restricted panel?
- What is the turnover/cost sensitivity within this biased panel?
- Which results are entirely explained by market beta?

## Not permitted questions

- Does this prove a survivorship-free strategy?
- Can this be deployed?
- Does this establish historical S&P 500 alpha?

## Exact restricted universe

- 503 current-universe tickers in the raw panel
- 466 tickers have all 2,532 sessions
- 37 tickers have incomplete price rows and are excluded from the restricted
  exploratory universe
- manifest: `docs/research/restricted_universe_full_coverage_2026-10-28.csv`

Coverage inside the 466-ticker manifest is 100% by construction; that is not
evidence of historical universe coverage.
