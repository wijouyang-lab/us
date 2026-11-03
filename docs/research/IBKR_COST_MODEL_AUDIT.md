# IBKR Pro Tiered Cost Model Audit

Date: 2026-11-03
Scope: research cost accounting only. No order routing, no live execution.

## 1. Layers

`tools/research/ibkr_costs.py` now exposes:

```text
forward_estimate      current published IBKR schedule, for prospective estimates
historical_backtest   current-rate approximation for 2007-2026 backtests
```

Rates:

| Component | Value |
|---|---|
| Commission | $0.0035/share, min $0.35, max 1% |
| SEC | 0.0000206 × sell notional |
| TAF | $0.000166/share sell, max $8.30 |
| TAF holiday | 2026-10-01..2026-12-31 = 0 |
| CAT | $0.000003/share |
| Clearing | $0.00020/share, 0.5% notional cap assumption |
| Exchange/pass-through | $0.00010/share base; 0..$0.00030 range |
| Slippage | separate 1/3/5/10/20 bps |

CAT did not exist in 2007; SEC/clearing rates changed over time. Therefore the
`historical_backtest` layer is explicitly **current-rate approximation**, not a
reconstruction of historical IBKR venue bills. The effect is bounded by the
cost-only recalculation below.

## 2. Cost-only recalculation

New per-leg fees were applied to the existing trade ledgers; slippage was kept
unchanged. Signals, weights, NAV, drawdown and risk gates were not changed.

| Case | Old cost | New cost | Difference |
|---|---:|---:|---:|
| #451 A | $4,621.04 | $4,618.78 | -$2.26 |
| #451 B | $5,726.25 | $5,728.58 | +$2.32 |
| #451 C | $1,034.94 | $1,034.48 | -$0.46 |
| #452 D PIT | $1,141.32 | $1,138.51 | -$2.80 |
| #453 E | $3,872.06 | $3,864.15 | -$7.91 |
| #454 F PIT | $1,497.84 | $1,494.88 | -$2.96 |

Largest impact is E at **-$7.91**, less than 0.02% of a $50,000 account over 19
years. Cost-after CAGR differences are below 0.01%/yr and cannot change any
NO-GO decision.

This is a cost-only recalculation. Full NAV/statistical reruns for #451-#454 were
not performed; those reports are marked as using the pre-calibration cost layer.
G (#455) uses the calibrated model end-to-end.

## 3. Interpretation

- Do not compare G's cost line directly with #451-#454 totals; G uses the new
  layered model.
- The new model adds CAT/clearing but lowers SEC from the old 0.0000278 to
  0.0000206; net impact is small.
- Venue/pass-through remains an assumption band, not a claim of actual historical
  SmartRouting fills.
