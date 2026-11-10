# E Pre-registration: Real-Yield 63-Session Shock Filter

Frozen before running E.

Universe: SPY, IEF, TLT, BIL. $50,000, long-only, no leverage.

Signal:

```text
real_yield_change_63 = latest_visible_DFII10 - DFII10 63 SPY sessions earlier
```

Allocation:

- change >= 0.50 pp: BIL 100%;
- otherwise: SPY 70%, IEF 15%, TLT 15%;
- missing/invalid: BIL 100%.

Monthly at the last SPY session. Macro value must be visible by the prior full
SPY session; next SPY session raw Open execution. No other window or threshold
is tested. Cost: IBKR Pro Tiered simulation, 5 bps/leg base, 1/3/5/10/20 bps
sensitivity.

The DFII10 current and 63-session base values must come from the same ALFRED
vintage; no revised history is allowed to enter an earlier decision. Missing
PIT data fails closed to BIL.

Evaluation: positive excess after costs, HAC/BH support vs BIL, max DD <= 15%,
no single-stage dependence, sufficient trades/exposure, reproducible accounting.
