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

## Start accumulating genuine point-in-time captures

The research branch includes a one-shot bootstrap capture workflow: [Research Event Factor Capture](https://github.com/wijouyang-lab/us/actions/workflows/research-event-factor-capture-once.yml). Updating the workflow file on this branch triggers a capture; the workflow also defines `workflow_dispatch` for future use if it is available from the repository default branch. Each run collects the allowlisted official RSS feeds and Treasury nominal/real curve snapshots, stores immutable capture files, updates the versioned event archive, and uploads a 90-day evidence artifact. It does not run on a schedule and does not call the production scanner.

Run it repeatedly over time to accumulate genuine first-seen timestamps. A single capture is not a historical event dataset. The workflow deliberately does not invent earnings surprise labels, reconstruct historical consensus, or infer historical availability from today's downloads. Event labels still require documented human review before event-factor evaluation.

## Audit data readiness before scoring

Before generating any signal panel, audit the archive and (optionally) the exact
decision timestamps used in the proposed evaluation:

```bash
python -m tools.research.audit_pit_event_data_readiness \
  --archive data/research/event-capture/event_archive.json \
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
  --default-max-age-days 30 \
  --max-age-days-by-type '{"macro_release":30,"policy":14,"central_bank":14}' \
  --output data/research/event_signals.csv \
  --report data/research/event_signal_panel_report.json
```

The panel applies a 30-day default freshness cap, with the macro-release and policy-family overrides shown above. This prevents old items retained in rolling RSS feeds from being scored as fresh events. Review and predeclare family-specific freshness windows before final testing. The output signal CSV is compatible with the event factor backtest. Missing or ineligible event coverage remains missing, never filled with zero.

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

The comparison restricts both portfolios to the same ticker/decision rows with event coverage and sufficient
prior prices. The baseline is trailing close-to-close momentum using price sessions
strictly before the decision calendar date. The comparison report also includes a paired event-minus-momentum mean-return difference with a Newey-West HAC confidence interval using a predeclared maximum lag of `horizon - 1`, when at least three paired decision dates are available. This is an asymptotic uncertainty diagnostic for serial dependence from overlapping returns, not proof of alpha; small samples, strategy selection, and residual dependence remain limitations.

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

## Capture Treasury yield curve values

Capture the official daily par yield curve as a separate immutable research snapshot:

```bash
python -m tools.research.treasury_yield_curve_capture \
  --year 2026 \
  --output data/research/captures/treasury_yield_curve_2026.json
```

The default output contains nominal per-maturity yields, 2-year/10-year and 3-month/10-year spreads, and daily changes where both adjacent observations exist. To capture real (inflation-protected/TIPS-derived) yields instead, use `--curve-type real` and a separate output path. Real yields cover 5-, 7-, 10-, 20-, and 30-year maturities; they do not produce the nominal 2s10s/3m10y spreads. Empty values stay null. This is a manual collector and does not change the production scanner or create a scheduled workflow.

**Point-in-time warning:** the Treasury feed can return historical rows today, but a current download does not establish when each old value was first available. Each row records the actual retrieval time and may only be used for decisions at or after that time unless a separately validated historical availability timestamp exists. Do not backtest earlier dates using this file as if it were archived contemporaneously.

## Attach Treasury macro features to decision timestamps

The Treasury capture commands create immutable snapshots, and a historical download is not evidence that the values were available historically. To make that constraint explicit when preparing a feature panel, use:

```bash
python -m tools.research.build_treasury_macro_panel \
  --decisions data/research/decision_timestamps.csv \
  --nominal data/research/captures/treasury_yield_curve_2026.json \
  --real data/research/captures/treasury_real_yield_curve_2026.json \
  --output data/research/treasury_macro_panel.csv \
  --report data/research/treasury_macro_panel_report.json
```

The decision CSV must contain timezone-aware ISO-8601 `decision_at` values. The output retains original decision columns and adds nominal 2y/3m/10y yields, 2s10s and 3m10y slopes, real 10y yield, and a nominal-minus-real 10y inflation-compensation proxy. Each snapshot is eligible only at or after its actual retrieval timestamp; observation dates after a decision date are excluded. Missing yields remain null. Separate nominal/real age columns let a later evaluation apply a predeclared staleness limit. Review the JSON report before evaluation; this utility does not generate a trade signal or prove alpha.

## Compare event-factor performance across Treasury curve regimes

After building the strict PIT macro panel, run a predeclared descriptive regime split:

```bash
python -m tools.research.event_factor_macro_regime \
  --signals data/research/event_signal_panel.csv \
  --prices data/research/prices.csv \
  --macro-panel data/research/treasury_macro_panel.csv \
  --output data/research/event_factor_macro_regime_report.json \
  --max-feature-age-days 5
```

The tool compares event-factor portfolios with their paired price-only momentum baseline separately when the nominal 10y-minus-2y spread is below zero (inverted) and at/above zero (non-inverted). The zero-basis-point threshold and five-day maximum feature age are explicit defaults, not optimized parameters. Change them only as a predeclared research design before examining the final test block. Unavailable, stale, and missing macro rows are excluded rather than filled. Small or empty regime samples remain insufficient-data results, not evidence of no effect. This descriptive split alone cannot establish causal impact or alpha.

## Build a nominal-minus-real inflation-compensation proxy

After capturing separate nominal and real Treasury snapshots, join common observation dates without interpolation:

```bash
python -m tools.research.treasury_breakeven_proxy \
  --nominal data/research/captures/treasury_yield_curve_2026.json \
  --real data/research/captures/treasury_real_yield_curve_2026.json \
  --output data/research/captures/treasury_breakeven_proxy_2026.json
```

The maturity spread is calculated as nominal yield minus real yield, in basis points. This is an **inflation-compensation proxy**, not a pure expected-inflation estimate: inflation-risk and liquidity premia can contribute. The output is only usable at or after the later of the two snapshots' actual retrieval timestamps. Historical observation dates do not reconstruct historical point-in-time availability; do not use these rows in earlier backtests without separately validated vintage timestamps.

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
