# Strategy Lab

Read-only research dashboard for comparing strategy families in `wijouyang-lab/us`.

- Standalone `strategy-lab.html`; does not invoke scans or modify production scores, stops, portfolio ledger, or order logic.
- Reads only committed research outputs (`quant_research_status.json`, `quant_factor_validation_report.json`, and `quant_factor_validation.csv`).
- Does not calculate strategy Sharpe from factor IC or invent missing strategy returns. Strategy-level Sharpe remains blank until a reproducible portfolio-return series and its provenance are published.
- Complete-history comparison is marked unavailable while historical universe/data-quality gates are not met.

Current committed research artifacts do not provide a fresh, validated, complete-history return series for every strategy family. The page therefore displays data maturity and factor validation diagnostics, and explicitly identifies blockers instead of presenting fabricated ranks.


## Existing backtest diagnostic table

The page also reads `docs/UNIFIED_MULTI_STRATEGY_RESEARCH_STATUS.md` and parses the seven rows under “Test set (10 bps per side)”. These values are presented as historical diagnostics only. The source report explicitly says the 10-year PIT coverage gate failed, and the rough Sharpe values have only 24 non-overlapping test observations. They are not eligible for a current full-history strategy ranking or production selection. The Strategy Lab must continue to show the data-quality hold until a fresh, provenance-tracked report passes the PIT/universe gates.
