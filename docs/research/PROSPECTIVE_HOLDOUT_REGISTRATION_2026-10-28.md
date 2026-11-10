# Prospective Holdout Registration 鈥?Low-Frequency Five-Factor Check

Registered: 2026-10-28
Research only. No production scanner, portfolio, or trading change.

## Purpose

The historical 2-year check did not find a factor passing BH q < 0.05. This
registration prevents a post-hoc factor or direction change from being called a
confirmation.

## Frozen design

- Universe: the existing PIT snapshot pipeline, unchanged.
- Factors and directions (fixed before any post-registration return is observed):
  - `ATR_Pct`: long low, short high.
  - `Realized_Volatility_20D_Pct`: long low, short high.
  - `Momentum_60D_Pct`: long high, short low.
  - `RSI`: long low, short high.
  - `Volume_Ratio_20D`: long high, short low.
- Forward horizon: 20 trading sessions.
- Rebalance: every 20th session, phase 0.
- Portfolio construction: cross-sectional quintiles, long Q5 / short Q1,
  equal-weight within leg.
- Return treatment: 1%/99% winsorized forward return.
- Costs: 5 bps one way, full two-leg turnover each rebalance.
- Multiplicity: Benjamini-Hochberg across the five fixed tests.
- Significance: q < 0.05.
- Minimum evidence: at least 12 non-overlapping post-registration rebalances
  with mature 20-session labels.

## Evaluation boundary

- Registration data cutoff: 2026-10-28.
- The first eligible rebalance is the first trading session after the cutoff.
- Pre-registration data may be reported as historical context, but not counted
  as holdout evidence.
- Any change to factor, direction, horizon, costs, rebalance phase, or
  significance rule creates a new registration.
- No selective stopping based on interim results.

## Decision rule

If no factor reaches q < 0.05 after the minimum evidence and mature labels, the
research question is closed as **no validated deployable alpha** for this
free-data panel. Production remains unchanged.

If a factor reaches the threshold, it still requires execution, capacity,
regime, and data-coverage review before any production discussion.
