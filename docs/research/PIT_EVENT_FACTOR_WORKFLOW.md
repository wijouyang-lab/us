# Point-in-time event factor research workflow

This workflow is research-only. It does not change the production scanner, ranking,
external trigger, portfolio construction, or trading behavior.

Before interpreting family coverage, consult the [free official event-source inventory](PIT_EVENT_SOURCE_INVENTORY.md), which distinguishes implemented adapters from important gaps such as BEA PCE/GDP and verified company earnings surprises.

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
   - `label_review_status`: `reviewed` or `validated` only after an actual review
   - `label_reviewed_at_utc`: timezone-aware timestamp for when that review occurred
   The audit does not treat in-range numeric scores alone as validated labels. The
   pipeline deliberately does not infer these labels from headlines. Label review
   timestamps document annotation provenance; they do not by themselves prove that
   a reviewer was independent or that the annotation was available at each historical
   decision time.

For a consistent annotation rubric, use the companion [PIT event label annotation guide](PIT_EVENT_LABEL_ANNOTATION_GUIDE.md). It defines direction/impact scales, review provenance, and safeguards against hindsight leakage.

## Audit data readiness before scoring

Before generating any signal panel, audit the archive and (optionally) the exact
decision timestamps used in the proposed evaluation:

```bash
python -m tools.research.audit_pit_event_data_readiness \
  --archive data/research/event_archive.json \
  --decisions data/research/decision_times.csv \
  --output data/research/event_data_readiness.json
```

The report counts event families and sources, missing required metadata, timestamp
ordering problems, duplicate version IDs, direction/impact label coverage, and
point-in-time eligibility for each decision time. Use a fixed `--audited-at`
timestamp when a reproducible audit snapshot is required.

A `review_required` result is not proof that annotations are trustworthy or that
the factor has predictive power. `blocked_*` and `fail_*` statuses mean the
archive is not ready for empirical evaluation. The report always leaves
`empirical_alpha_established` and `production_activation_allowed` false; neither
unit-test success nor data completeness enables production trading.

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
ineligible event coverage remains missing, never filled with zero.

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

Do not select the best grid cell and report it as an unbiased result. Freeze score
definitions and parameters before the final test. Report coverage, timestamp eligibility,
turnover, costs, drawdown, and an exposure-matched benchmark when data permit.

## Compare with a price-only baseline

Both strategies use the same ticker/decision rows with event coverage and sufficient
prior prices. The baseline is trailing close-to-close momentum using price sessions
strictly before the decision calendar date.

```bash
python -m tools.research.event_factor_compare_price_baseline \
  --signals data/research/event_signals.csv \
  --prices data/research/prices.csv \
  --lookback 20 --horizon 20 --cost-bps-per-side 5 \
  --output data/research/event_vs_momentum.json
```

## Chronological walk-forward evaluation

Run the fixed chronological train/validation/test evaluation after freezing score
definitions and cost assumptions:

```bash
python -m tools.research.event_factor_walk_forward \
  --signals data/research/event_signals.csv \
  --prices data/research/prices.csv \
  --lookback 20 --horizon 20 --cost-bps-per-side 5 \
  --train-fraction 0.6 --validation-fraction 0.2 \
  --output data/research/event_walk_forward.json
```

The tool keeps contiguous time blocks, removes the last horizon decision timestamps
from the train and validation blocks to reduce cross-boundary overlap of forward-return
labels, and reports each split separately. Only the test block is the final OOS
diagnostic. The purge is based on decision timestamps and is only an approximation
to trading-session overlap; it does not guarantee independent returns. The tool does
not fit parameters or choose the best configuration.

## Event-family ablation

The signal panel also emits `event_score_family__<family>` and
`event_coverage_family__<family>` columns for each configured family. Run the
family evaluator to compare each family's score with a price-only momentum
baseline on that family's own paired ticker/decision rows:

```bash
python -m tools.research.event_factor_family_ablation \
  --signals data/research/event_signals.csv \
  --prices data/research/prices.csv \
  --lookback 20 --horizon 20 --cost-bps-per-side 5 \
  --output data/research/event_family_ablation.json
```

Families may have different coverage universes. Their raw returns must not be
ranked against one another as if they shared identical observations. For a stricter
comparison, run the common-universe evaluator:

```bash
python -m tools.research.event_factor_common_universe \
  --signals data/research/event_signals.csv \
  --prices data/research/prices.csv \
  --lookback 20 --horizon 20 --cost-bps-per-side 5 \
  --output data/research/event_family_common_universe.json
```

This keeps only ticker/decision rows where every configured family has available
coverage and a finite score, then compares all families on those same rows before
price-history eligibility. The stricter universe may be much smaller and may
overrepresent events covered by every source, so report its row count and coverage.
Missing family labels remain missing. This evaluator is research-only and does not
activate production signals.


TreasuryDirect auction announcement/result headlines are included in the manual capture. They are event observations only; do not treat the headlines as numeric auction signals. A separate, validated adapter is still needed for bid-to-cover ratios, auction tails, and Treasury yield-curve changes.

## Current limitations

- The score is a transparent weighted aggregation of explicit, externally validated
  labels, not a trained or validated predictive model.
- Historical first-seen times cannot be reconstructed from current RSS/SEC backfills.
  Meaningful PIT evaluation requires prospective archives or validated historical data.
- The backtest uses a close-price proxy and overlapping holding periods; its Sharpe
  estimate is not adjusted for dependence.
- The initial benchmark field is a data-presence check, not an alpha estimate.
- No live collection or empirical event-factor alpha claim is implied by passing unit
  tests. Production signal generation remains disabled.
