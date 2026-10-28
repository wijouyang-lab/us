# Formula Factor Walk-Forward Evaluation (Research Only)

The generator at `tools/research/formula_factor_discovery.py` now has a companion evaluator:
`tools/research/run_formula_factor_validation.py`.

Example (use an existing experiment backtest CSV; no download is performed):

```bash
python tools/research/run_formula_factor_validation.py \
  --input /tmp/experiment/backtest.csv \
  --output-dir /tmp/experiment/formula-results \
  --max-base-factors 8 --cost-bps 5
```

The evaluator:
- uses the existing dated factor columns and forward-return labels;
- excludes identifiers, metadata, `Forward_Return_*`, `WIN_*`, and common target labels from candidate inputs;
- reports daily Spearman IC, ICIR, daily Q5-Q1 spread, approximate spread after one-way costs on both legs, and positive-spread-day rate;
- divides observed dates into three chronological evaluation folds and applies a conservative horizon-sized date embargo at the start of folds 2 and 3;
- applies Benjamini-Hochberg FDR correction to approximate IC significance diagnostics within each horizon;
- writes a flat CSV and detailed JSON, without touching production files.

Important limitations: formula generation is cross-sectional and parameter-free, so the folds measure temporal stability rather than fitted-model generalization. Forward-return labels may overlap within a fold; the date embargo only addresses fold boundaries, not all within-fold dependence. The cost-adjusted spread is an approximation and omits turnover, borrow fees, capacity, slippage, and portfolio-level compounding. Treat results as exploratory; do not promote factors to production without a separate, stricter review and independent holdout.
