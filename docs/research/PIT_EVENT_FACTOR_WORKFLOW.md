# Point-in-time event factor research workflow

This workflow is research-only. It does not change the production scanner, ranking,
external trigger, portfolio construction, or trading behavior.

## Data requirements

1. Capture normalized events prospectively using `tools/research/run_event_capture_cycle.py`.
2. Keep the generated `event_archive.json` immutable/versioned. The archive must contain
   genuine `first_seen_at_utc` timestamps recorded when the collector actually observed
   the event. Historical publication dates alone cannot reconstruct historical first-seen.
3. Use a historically valid ticker universe for each period. A current S&P 500 list used
   across past dates creates survivorship bias.
4. Direction and impact annotations must be reviewed/validated before use:
   - `direction_score`: numeric value from -1 (negative) to +1 (positive)
   - `impact_score`: numeric value from 0 (irrelevant) to 1 (high impact)
   The pipeline deliberately does not infer these labels from headlines.

## Build a point-in-time signal panel

Create a CSV with one column `decision_at` containing timezone-aware timestamps,
a universe CSV with `ticker` and optional `sector`, and a JSON family-weight mapping.
For example, weights JSON:

```json
{
  "earnings": 1.0,
  "company_news": 0.5,
  "macro_release": 0.8,
  "policy": 0.7
}
```

Run:

```bash
python -m tools.research.build_pit_event_signal_panel \
  --archive data/research/event_archive.json \
  --universe data/research/universe_pit.csv \
  --decisions data/research/decision_times.csv \
  --weights data/research/event_family_weights.json \
  --output data/research/event_signals.csv \
  --report data/research/event_signal_panel_report.json
```

The output signal CSV is compatible with the event factor backtest. Missing or
ineligible event coverage remains missing and is excluded, never filled with zero.

## Evaluate score tails and cost/horizon sensitivity

First run a single declared configuration:

```bash
python -m tools.research.event_factor_backtest \
  --signals data/research/event_signals.csv \
  --prices data/research/prices.csv \
  --horizon 20 --cost-bps-per-side 5 \
  --output data/research/event_backtest.json
```

Then evaluate a predeclared sensitivity grid:

```bash
python -m tools.research.event_factor_cost_sensitivity \
  --signals data/research/event_signals.csv \
  --prices data/research/prices.csv \
  --horizons 5,10,20 --costs-bps 0,5,10,20 \
  --output data/research/event_sensitivity.json
```

Do not select the best grid cell and report it as an unbiased result. Use a
chronological train/validation/test split, freeze score definitions before the
final test, compare with a price-only baseline, and report coverage, timestamp
eligibility, turnover, costs, drawdown, and exposure-matched benchmark results.

## Current limitations

- The score is a transparent weighted aggregation of explicit labels, not a
  trained or validated predictive model.
- The backtest uses a close-price proxy and overlapping holding periods; its
  Sharpe estimate is not adjusted for dependence.
- The optional benchmark field in the initial backtest is a data-presence check,
  not an alpha estimate.
- No live collection or empirical event-factor alpha claim is implied by passing
  unit tests. Production signal generation remains disabled.


## Compare with a price-only baseline

After generating the event-score panel, run a paired comparison. Both strategies use
the same ticker/decision rows with event coverage and sufficient prior prices, so
the comparison is not driven merely by different coverage universes.

```bash
python -m tools.research.event_factor_compare_price_baseline \
  --signals data/research/event_signals.csv \
  --prices data/research/prices.csv \
  --lookback 20 --horizon 20 --cost-bps-per-side 5 \
  --output data/research/event_vs_momentum.json
```

The baseline is a simple trailing close-to-close momentum score, using only price
sessions strictly before the decision calendar date. This is a research comparator,
not a production strategy. The comparison remains preliminary until evaluated across
multiple chronological out-of-sample decision dates and against exposure-matched
benchmark returns.
