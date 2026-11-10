# P7.1 — Updated scores and persistent research shadow

Date: 2026-11-06
Status: **P7_STRATEGY_RESEARCH · RESEARCH_ONLY · PIT_BACKTEST_BLOCKED**

No PAPER-50000 read/write, no IBKR, no real order. This is research simulation.

## 1. New SEC facts actually feed the Value score

`refresh_scores_p71.py`:

- takes the 93 `UPDATED_FROM_SEC_COMPANYFACTS` rows;
- replaces the actual Value inputs (net income, equity, revenue, CFO, CapEx,
  FCF) rather than only top-of-book display;
- recomputes P/B, P/S, Earnings Yield, FCF Yield and derived PE;
- re-runs the existing peer-group winsorized percentile and four-factor
  composite;
- writes a **new version**; P6 and P7 first-pass rankings are preserved.

Result:

```text
updated rows: 93
value rows:   5,453
value ranked:   811
old top50:       50
new top50:       50
```

New top 20:

```text
CRMT, WETH, LIVE, CAAS, CTRM, EBS, NUS, MNDO, PSFE, BOSC,
ABG, USNA, NATR, IMMR, GPI, CRWS, XTNT, CCS, EFOR, EDUC
```

New entrants to Top50 include `CNMD, M, SHOE, SKYW, SNT, PBH, DSWL, NRDS,
TRIP, EYE, WGO`.

Value strategy still has exactly 13 fully-gated candidates; the selected set is
the same, but scores/order changed. No threshold was relaxed.

### Quality and GARP

The refreshed fact table does not have the balance-sheet/asset history needed
for ROA, liabilities/assets, or multi-year growth. Those factors are therefore
**not recomputed and not zero-filled**. The status is:

```text
NOT_RECALCULATED_MISSING_ASSETS_OR_HISTORY
```

Their strategies remain `NOT_LAUNCHABLE` (<10). This is preferable to fabricating
new Quality/GARP scores from partial data.

Files:

```text
data/universe/p7/value_rankings_p71.csv
data/universe/p7/value_top50_p71.csv
data/universe/p7/value_score_comparison_p71.csv
data/universe/p7/p71_score_refresh_summary.json
```

## 2. Persistent shadow state

`shadow_portfolio.py` now persists:

```text
data/universe/p7/shadow_state.json
data/universe/p7/shadow_positions.csv
data/universe/p7/shadow_fills.csv
data/universe/p7/shadow_nav.csv
```

Behavior:

- completed fill is not overwritten;
- no repeated commission or duplicate fill;
- one official NAV row per session;
- offline/default run preserves a completed state;
- pending run is safe to repeat;
- no PAPER-50000 source or destination.

## 3. First fill status

Current next session:

```text
signal date:  2026-11-05
next session: 2026-11-06
```

The yfinance provider does **not yet provide a complete 2026-11-06 OHLCV bar**
in this run. Therefore the shadow remains:

```text
status: PENDING_NEXT_SESSION
first fill: none
```

This is deliberate: using 2026-11-05 close as the next-session open would be
look-ahead. The workflow will fill only after a complete session; missing data
does not produce a fake fill or return.

Current NAV row:

```text
date: 2026-11-05
nav: 50000
cash: 50000
positions_value: 0
status: PENDING_NEXT_SESSION
```

## 4. Daily shadow workflow

Added:

```text
.github/workflows/p7-shadow-daily.yml
```

- `workflow_dispatch` only;
- branch input defaults to `research/invest-terminal-v1`;
- `concurrency` prevents duplicate shadow updates;
- runs `shadow_portfolio --refresh`, benchmark alignment, snapshot, P7 tests;
- commits only `data/universe/p7` and the snapshot on the research branch;
- uploads `p7-shadow-daily` artifact;
- no main change, no merge.

## 5. Benchmarks

`benchmark_nav.csv` is date-aligned to the official shadow NAV dates:

```text
SPY, QQQ, IWM
EQUAL_WEIGHT = PENDING_TARGET_REFERENCE
```

No missing date is filled with zero return. Current shadow has only the
2026-11-05 initial date, so the benchmark table has only that aligned date until
the first completed next session.

## 6. Strategy Lab

The snapshot includes:

- updated P7 strategy status;
- target weights;
- actual simulated positions (none yet);
- cash and fees;
- shadow status and NAV;
- benchmark alignment;
- explicit `RESEARCH_ONLY` label.

Target / pending / filled are distinct states. Current positions are
`PENDING_NEXT_SESSION`, not filled.

## 7. Boundaries

- No first simulated fill is claimed because no complete 2026-11-06 data exists.
- No Alpha, PIT backtest, Sharpe or out-of-sample claim.
- Quality/GARP remain not launchable and not recomputed from incomplete data.
- PR #512 remains Draft and unmerged.
