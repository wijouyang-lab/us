# D Pre-registration: Yield Curve and Financial Conditions Allocation

Frozen before any D backtest was run. Branch:
`research/macro-curve-financial-conditions`.

## Data

- FRED `T10Y3M`, 10Y-3M Treasury spread.
- Chicago Fed `NFCI`, National Financial Conditions Index.
- `NFCICREDIT` is audited but **not used** in the primary rule; it is a
  diagnostic series only because its historical vintage coverage is not assumed.
- `BAMLH0A0HYM2` is not used; FRED's current series is too short for a 2007
  sample and is not a substitute for a long PIT credit series.
- PIT source: ALFRED vintage files. Monthly signal uses the last Monday vintage
  on or before the month-end session. This is deliberately conservative: it
  avoids using a release that occurred after the month-end close.
- PIT coverage begins 2014-01-27 for both series. 2007-2013 is **not** claimed
  as point-in-time; it can only be exploratory using revised history.
- Missing macro values: hold BIL; never forward-fill.

## Rule

At the last SPY session of each month, using the latest PIT values:

```text
curve_inverted = T10Y3M < 0
financial_tight = NFCI > 0
```

| State | Condition | Allocation |
|---|---|---|
| Normal | curve >= 0, NFCI <= 0 | SPY 70%, IEF 15%, TLT 15% |
| Late cycle | curve < 0, NFCI <= 0 | IEF 40%, TLT 30%, SPY 15%, BIL 15% |
| Tight | curve >= 0, NFCI > 0 | IEF 30%, TLT 20%, BIL 50% |
| Stress | curve < 0, NFCI > 0 | BIL 100% |

Execution: next SPY session raw Open. Monthly only. Long-only, no leverage.
$50,000 initial equity; IBKR Pro Tiered simulation; 5 bps/leg base slippage;
1/3/5/10/20 bps sensitivity.

No threshold search, no alternate state map, no parameter rescue. If the rule
fails, record FAILED.

## Evaluation gates

1. Positive excess over BIL after costs.
2. HAC/BH statistical support vs BIL.
3. Max drawdown <= 15%.
4. Not dependent on one stage.
5. Enough exposure/trades for inference.
6. Reproducible NAV, order legs, fees, dividend accounting.

Primary evidence: PIT 2014-2026. Exploratory only: revised-history 2007-2026.
