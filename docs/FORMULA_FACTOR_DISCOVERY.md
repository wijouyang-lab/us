# Mathematical Formula Factor Discovery (Research Only)

## Purpose

The formula generator creates a bounded, deterministic candidate set from
point-in-time factor columns. It is a hypothesis-generation tool, not a strategy
optimizer and not a production scoring change.

For each date (t), a base factor is standardized across the available universe:

`z_t(x_i) = (x_i - mean_t(x)) / std_t(x)`

The current candidate grammar is deliberately small:

- `z(x)`: normalized base factor
- `z(x) - z(y)`: relative strength / factor balance
- `z(x) * z(y)`: interaction
- `z(x) / (1 + |z(y)|)`: condition- or risk-scaled factor

The division form is bounded against a zero denominator. Constant cross-sections
produce missing values rather than fabricated zeros. The module does not read
forward-return columns, fit parameters, or evaluate user-supplied code.

## Required validation before interpreting results

1. Use only features available by the actual decision timestamp; use point-in-time
   universe membership and avoid survivorship/look-ahead bias.
2. Freeze the candidate grammar and evaluation protocol before inspecting
   holdout results.
3. Evaluate candidate IC and long-short spreads on chronological walk-forward
   windows; purge overlapping forward-return labels and apply an embargo where
   appropriate.
4. Compare against simple baselines (including momentum and ATR-related
   candidates) on the same universe and dates.
5. Include turnover, realistic transaction-cost assumptions, capacity/liquidity
   filters, regime stability, and multiple-testing correction (for example,
   a predeclared family-wise or false-discovery-rate procedure).
6. Report all tested candidates and failures, not only the best result.

The generator is not wired into the production scanner, ranking, portfolio, or
trading ledger. Generated candidates are not evidence of alpha; the existing
event-factor data/label readiness gates remain in force.
