# G Pre-registration: Fixed 20% QQQ / 80% BIL

Frozen before the G backtest.

```text
QQQ 20%, BIL 80%
```

$50,000, long-only, no leverage, no forecast signal. Monthly restore at the last
common session; next session raw Open. Initial build at raw Open. Integer shares,
residual cash. Dividends credited on ex-date to shares held before the ex-date;
no automatic reinvestment. Calibrated IBKR Pro Tiered costs plus 5 bps/leg base
slippage, with 1/3/5/10/20 bps sensitivity.

This is a fixed risk-budget implementation baseline, not a timing strategy and
not alpha. Because a prior screen was seen, the historical run is explicitly
**exploratory / implementation validation**, not a pristine confirmatory test.
No weight search will be performed. MaxDD gate remains 15%. If it passes, the
label is `RISK_BUDGET_BASELINE / RESEARCH_CANDIDATE`, not deployable alpha.
