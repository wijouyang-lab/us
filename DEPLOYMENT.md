# Deployment

Replace these repository code/config files:

- scan.py
- review.py
- evolve.py
- scan_us_option_engine.py
- strategy_params.json
- .gitignore
- .github/workflows/scan.yml
- .github/workflows/review.yml
- .github/workflows/evolve.yml

Do not overwrite newer runtime history with the snapshot CSV/HTML files from an older local archive. Keep the current GitHub versions of trade_history.csv, review_history.csv, option_strategies.csv, report.html and review_report.html unless you intentionally want to restore those files.

After deployment:

1. Run Scan once.
2. Confirm the log prints the Regime line, hard-gate count, Quant scores and (when eligible) option generation.
3. Run Review.
4. Confirm Review writes the new report and commits the generated files.
5. Run Evolve only after enough new closed/reviewed observations have accumulated; it is guarded by an out-of-sample threshold check.
