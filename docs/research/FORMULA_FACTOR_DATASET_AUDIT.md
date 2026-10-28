# Formula-factor dataset structural audit

Run before interpreting formula-factor metrics:

```bash
python tools/research/audit_formula_factor_dataset.py \
  --input research_backtest_sp500_pit_2y.csv \
  --output formula-factor-results/dataset_audit.json
```

The audit reports date coverage, ticker coverage by date, duplicate date/ticker rows, numeric feature missingness, forward-return label distributions, and suspicious labels outside +/-100%. It does not mutate the dataset or silently drop records.

This is not proof of point-in-time correctness. Historical constituent membership and the timestamp at which each feature became observable require separate provenance evidence. Any warnings must be reviewed before promoting research findings.
