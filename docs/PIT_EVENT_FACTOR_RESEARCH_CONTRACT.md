# Point-in-Time Event Factor Research Contract

Status: research design only. This document does not change the production scanner, ranking, portfolio construction, scheduler, or trading behavior.

Related tracking issue: https://github.com/wijouyang-lab/us/issues/269

## Objective

Test whether news, earnings, macro releases, and policy/central-bank communications add repeatable out-of-sample value beyond the frozen price-only baseline. Event inputs must be evaluated as information that was actually available at each historical decision time—not as facts reconstructed with hindsight.

## Non-goals and safety boundary

- Do not change `scan.py`, `.github/workflows/scan.yml`, `review.py`, or `.github/workflows/review.yml` as part of this research stage.
- Do not enable production feature flags or route event scores into live/paper decisions.
- Do not treat missing data as a neutral signal.
- Do not use a current article page, revised macro series, or current earnings calendar as proof that the same information was available historically.
- Do not merge research results into production without a separate review and explicit approval.

## Canonical event record

Store one immutable row per source event/version. Suggested fields:

| Field | Meaning | Rule |
|---|---|---|
| `event_id` | Stable internal ID | Deterministic hash of normalized source + source item ID/URL + version timestamp |
| `source` | Publisher or official source | Keep the original source identity |
| `source_event_id` | Provider ID, URL, accession, or release ID | Preserve when available |
| `event_type` | `company_news`, `earnings`, `macro_release`, `central_bank`, `policy`, `geopolitical`, `other` | Controlled vocabulary; unknown stays unknown |
| `published_at_utc` | Source publication timestamp | Null if not verifiable; never fabricate |
| `first_seen_at_utc` | Time our collector first observed the event | Immutable; critical for replay |
| `updated_at_utc` | Source update time, if supplied | Keep separate from original publication |
| `effective_at_utc` | Economic/decision effective time, if applicable | Separate from publication time |
| `headline` | Original headline or normalized text | Keep raw payload separately where licensing permits |
| `content_hash` | Hash of retrieved content | Enables change detection without storing prohibited text |
| `tickers` | Explicit company/security mappings | Empty/unknown is not the same as market-wide |
| `sectors` | Explicit sector mappings | Record mapping version |
| `source_quality` | Source-quality tier | Defined before evaluating returns |
| `payload_version` | Parser/schema version | Enables deterministic replay |
| `availability_status` | `available`, `timestamp_missing`, `mapping_missing`, `fetch_error`, `parse_error` | Missingness remains explicit |

All timestamps should be stored in UTC and displayed/decision-aligned in `America/New_York`. For macro releases, store the release's publication time and the series observation period separately. For earnings, store scheduled time, actual release time when verified, and the time the collector first saw it separately.

## Point-in-time eligibility

For a decision at time `T`, an event is eligible only if:

1. `first_seen_at_utc <= T`;
2. if a trustworthy publication timestamp exists, `published_at_utc <= T`;
3. any source update used by the feature was first observed by `T`;
4. ticker/sector mapping and parser version are those known at `T`, or are explicitly versioned and replayed without later knowledge;
5. the event has not exceeded a pre-registered freshness window for its event family.

If timestamps conflict or are missing, exclude the event from the primary point-in-time signal and count it in data-quality reporting. A separate sensitivity analysis may evaluate timestamp-missing records, but must never silently mix them into the primary result.

Do not forward-fill a future release into earlier rows. For revised macro data, use first-release vintages where available; otherwise mark the affected historical period as not point-in-time verifiable.

## Initial event families

1. **Company news:** positive/negative/uncertain/other; source quality and freshness; deduplicate syndicated copies.
2. **Earnings:** actual release availability, surprise only when both consensus and actual values are point-in-time valid, guidance/news tags; distinguish pre-market, intraday, and after-hours.
3. **Macro releases:** CPI/core CPI, PCE/core PCE, payrolls/unemployment, GDP, retail sales, ISM and other pre-registered releases; compare actual vs consensus only when consensus history is licensed/available and timestamped.
4. **Rates and central bank:** FOMC statements/minutes, scheduled decisions, press conferences, speeches, and verified policy communications; use release/statement timestamps rather than the date label alone.
5. **Fiscal/policy/geopolitical:** official announcements and attributable statements, with source confidence and explicit affected market/sector mapping.
6. **Market regime context:** rates, volatility, and broad-market reaction may be contextual covariates, but must not be double-counted as independent event alpha.

Start with deterministic metadata and simple, auditable classifications. Do not introduce an LLM sentiment score until a deterministic baseline, evaluation set, and reproducibility contract exist.

## Free-source-first ingestion

Prefer official/public sources where possible: SEC EDGAR filings and company investor-relations feeds for corporate disclosures; FRED and official BLS/BEA releases for macro series; Federal Reserve and U.S. Treasury releases for policy communications; and RSS feeds for general news. Check each provider's terms, rate limits, historical depth, and timestamp semantics before use. A free source is not automatically historically complete or suitable for backtesting.

## Feature table contract

One row per decision timestamp and instrument (or explicit market/sector scope), with:

- `decision_at_utc`, `ticker`, `feature_asof_utc`;
- event-family features (counts, freshness, source quality, direction/confidence where validated);
- `coverage_status` and per-family missingness flags;
- `source_snapshot_hash`, `parser_version`, `mapping_version`;
- frozen baseline features kept separate from event features.

Require `feature_asof_utc <= decision_at_utc`. Every feature row must be traceable to the exact eligible event IDs that produced it. A ticker with no event coverage must not receive an implicit zero/neutral event score.

## Evaluation plan

1. Freeze and checksum the existing price-only baseline before any tuning.
2. Define event labels, freshness windows, cost assumptions, and evaluation metrics before looking at final holdout results.
3. Use chronological walk-forward folds; fit thresholds/classifiers only on each training window and evaluate only on the subsequent window.
4. Compare: price-only baseline; each event family added separately; selected combinations; and event-family ablations.
5. Report net return/CAGR, volatility, Sharpe, max drawdown, turnover, transaction costs, exposure, coverage, timestamp completeness, event freshness, and missingness by fold.
6. Include SPY and exposure-matched SPY-plus-cash comparators where applicable. Match rebalance times and cost assumptions.
7. Report results by market regime and event family, but avoid selecting a model solely because one regime or one fold performs well.
8. Require a genuinely untouched final holdout and publish negative results as well as positive ones.

## Acceptance gates

- **Data integrity:** no eligible event occurs after its decision time; duplicate and revised items are handled deterministically; missing timestamps and mapping failures are visible.
- **Reproducibility:** same frozen input snapshot and code version produce the same feature rows and metrics.
- **Incremental value:** event overlay improves a pre-registered net-of-cost metric without unacceptable drawdown, turnover, or concentration; result persists across walk-forward folds and is not explained by higher exposure.
- **Operational robustness:** provider outages or rate limits degrade to explicit missing coverage, not invented neutral values or scanner crashes.
- **Production isolation:** no production behavior changes from research merges alone. A later, separate proposal must specify shadow-only observation, rollback, monitoring, and human approval before any activation.

## First implementation sequence

- [ ] Define event schema and timestamp eligibility helpers with deterministic unit tests.
- [ ] Build source adapters one at a time, starting with official structured releases and SEC/IR metadata.
- [ ] Save immutable raw/normalized snapshots with hashes and parser versions.
- [ ] Generate point-in-time features against existing historical decision timestamps.
- [ ] Produce coverage and leakage audit before running any performance comparison.
- [ ] Run walk-forward family-by-family experiments only after the audit passes.
