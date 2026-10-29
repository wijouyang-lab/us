# Qlib-inspired low-frequency strategy candidate

Status: research candidate only; not a production strategy.

## Rationale

The repository's existing fixed-factor test did not establish stable alpha. Rather than keep expanding bespoke infrastructure, this candidate borrows the useful *research pattern* from Microsoft Qlib: construct a diverse feature set, combine cross-sectional ranks, and evaluate a portfolio against a same-universe benchmark. It deliberately does not add Qlib as a dependency or copy a model result from another market.

Source inspiration: https://github.com/microsoft/qlib and its Alpha158 / formulaic-alpha research workflow.

## Strategy hypothesis

At each month-end close, rank eligible stocks by a fixed weighted blend:

| Feature | Weight | Intended effect |
|---|---:|---|
| 12-1 momentum | 35% | medium-term trend excluding the latest month |
| 100-day trend | 25% | trend confirmation |
| Low 60-day realized volatility | 20% | reduce risk concentration |
| 5-day reversal | 10% | avoid chasing very short-term moves |
| 20/60-day dollar-volume trend | 10% | prefer improving liquidity |

Select the top quintile, equal-weight, enter at next session open, and exit at the open 20 sessions after entry. The test begins 2023-01-01; weights are fixed rather than selected on the test period. Costs are modeled at 5 bps per unit of one-way turnover and should be stress-tested.

## Run

```bash
python -m tools.research.qlib_inspired_low_frequency_strategy \
  --price-panel price10y_1028.csv \
  --output-prefix docs/research/qlib_inspired_low_frequency_2026-10-30
```

The tool writes JSON and CSV results. It must be run against the existing local OHLCV panel; this repository integration does not claim the result has already been run.

## Guardrails

- Research only; no production scan, score, stop-loss, ledger, or order path is changed.
- Uses OHLCV-derived features only; no unsupported event or fundamental timestamps.
- Does not silently drop selected assets with missing forward labels; the affected rebalance is excluded.
- The current-universe price panel is survivorship-biased and not point-in-time.
- Reported monthly returns are serially dependent and are not independent statistical trials.
- A positive backtest alone does not authorize deployment. Require comparison with the current fixed-factor baseline, 10/20 bps cost sensitivity, and a separate untouched test period.
