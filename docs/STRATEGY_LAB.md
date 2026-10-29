# Strategy Lab

Read-only research dashboard for comparing strategy families in `wijouyang-lab/us`.

- Standalone `strategy-lab.html`; does not invoke scans or modify production scores, stops, portfolio ledger, or order logic.
- Reads only committed research outputs (`quant_research_status.json`, `quant_factor_validation_report.json`, and `quant_factor_validation.csv`).
- Does not calculate strategy Sharpe from factor IC or invent missing strategy returns. Strategy-level Sharpe remains blank until a reproducible portfolio-return series and its provenance are published.
- Complete-history comparison is marked unavailable while historical universe/data-quality gates are not met.

Current committed research artifacts do not provide a fresh, validated, complete-history return series for every strategy family. The page therefore displays data maturity and factor validation diagnostics, and explicitly identifies blockers instead of presenting fabricated ranks.
