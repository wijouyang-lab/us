# P12.4 closeout & M1 macro cross-sectional research handover

Date: 2026-11-17
Repository: `wijouyang-lab/us`
Status: P12.4 closed; next research track = macro-event-driven cross-sectional equity response
Operating constraints: research branch only; do not merge PRs; do not modify `main`; no purchase, VPS, IBKR, paper/shadow or production changes; free sources only; budget ceiling USD 20 unless user explicitly changes it.

## 1. P12.4 final disposition

P12.4.3 is accepted as complete by the project owner. The supplied verification states commit `45db23c14d7114d524324c78e34d10e1507a39d9`, CI full suite 1,404 passed / 1 skipped, focused tests 6 passed, with no raw data committed. The three statistical/timing defects were corrected: one-extra-day D5/D10/D20 horizons, US/Eastern explore/validate assignment, and independent D5/D20 8-K counts. Do not create P12.4.4.

Final scientific labels:
- Fundamental change: NO_SIGNAL.
- 8-K Item 2.02 AFTER_HOURS: NO_SIGNAL after clean overlap controls.
- 8-K Item 5.02 AFTER_HOURS: NO_SIGNAL after overlap controls.
- Tradable alpha: NOT_CLAIMED.
- Market-wide generalization: DATA_BLOCKED.
- P12.4 status: DESCRIPTIVE_ONLY.

Preserve branch `research/p12-event-fundamental-feasibility`, all P12.4.1/.2/.3 artifacts, raw local-only research data and manifests. No PR merge or main changes.

Commit existence was checked through GitHub; CI evidence supplied by the project owner. Do not confuse P12.4.3 CI with other earlier P12.4.2 runs.

## 2. Existing macro/event infrastructure found

- PR #271 merged: PIT event-factor foundation, normalized event records, first-seen timestamps, version archive, fail-closed missingness, BLS/Fed RSS collection scaffolding, macro surprise eligible only with demonstrably pre-release timestamped consensus. Important limit: archived SEC submissions/recent feeds do not create historical first-seen timestamps; BLS/Fed RSS timestamps are publisher metadata.
- PR #282 closed unmerged, draft: descriptive PIT event-response engine. Consumes supplied snapshots and price CSV; before-09:30 ET events may enter same-session open, at/after 09:30 enter next available session. Market-wide events use SPY proxy; no sentiment/signal claims. Its concept/code should be reviewed before reuse.
- PR #365 merged: event-response aggregates deduplicated by ticker + entry date + horizon to stop duplicate event rows sharing the same market return from masquerading as independent samples.
- PR #445 OPEN, not merged: `research/macro-event-response`, HEAD `c6e4fd1facca0489ac8590723a0475d4e26b5c09`, 16 files, CI run 41498820411 success. It added `tools/research/macro_event_response.py`, tests, events inventory, session alignment, audit, and `docs/research/MACRO_EVENT_RESPONSE.md`. Its status is DATA_BLOCKED / INCONCLUSIVE, not empirical failure.
- PR #445 report records 500 events: CPI 166 and Employment 166 only from 2007–2020 legacy archive, date-only without release times; FOMC 168 from 2007–2026 with 14:00 ET scheduled time. BLS live archive returned 403; legacy FDLP coverage ends in 2020. FOMC events align to next session because release is at 14:00 ET, but the time is scheduled/medium-confidence rather than independently verified first-seen time. Study is explicitly NOT_RUN_DATA_BLOCKED. No empirical significance or event-family ranking was produced.

PR URLs:
- https://github.com/wijouyang-lab/us/pull/271
- https://github.com/wijouyang-lab/us/pull/282
- https://github.com/wijouyang-lab/us/pull/365
- https://github.com/wijouyang-lab/us/pull/445

## 3. New research question

Can pre-event issuer characteristics and industry/firm exposures explain and predict *cross-sectional* differences in individual US stocks' response to macroeconomic releases, Federal Reserve policy decisions and major public policy speeches, over 1–20 trading sessions?

The target is individual-stock selection for a low-frequency strategy holding days to weeks, daily scans, broad US equity coverage where data supports it, balanced risk. Do not revert to a market-direction-only SPY study.

## 4. M1 deliverable: macro event & PIT readiness, before alpha tests

First make a source/event matrix with each event family, exact official URL, historical coverage, actual release timestamp confidence, first-seen/revision availability, market-data alignment, available surprise/consensus, ticker/sector linkage and blockers.

Start with event families:
1. Scheduled macro releases: CPI/core CPI, PCE/core PCE, Employment Situation/payrolls, unemployment, claims (only if historical timestamped observations can be supported).
2. Policy: FOMC decision/statement, SEP/dot plot, minutes, press conference, unscheduled Fed policy announcements.
3. Major official public speeches/testimony: Fed Chair and governors only where exact public timestamp and archived text/transcript are verifiable.

Do not broaden to every news headline. Do not infer historical exact publication time from date-only index. Do not represent a current revised series as the initial value. Separate:
- reference_period;
- release date and precise time with timezone;
- official publication/embargo time;
- collector first_seen_at;
- vintage/revision timestamp;
- actual value and consensus source/time;
- prior value as known immediately before release;
- source URL, version, hash and source role.

No surprise without timestamped pre-event consensus. No strict PIT replay from backfilled data with fictional first_seen_at. Where initial vintage is unavailable, label the feature unavailable and run only a clearly separated descriptive branch if useful.

## 5. Cross-sectional exposure hypotheses (pre-register; test, do not assume)

Build candidate *pre-event* exposures:
- Rate duration / discount-rate sensitivity: long-duration growth, valuation/profitability duration, debt maturity and floating-rate debt where PIT-supported.
- Funding/credit sensitivity: leverage, interest coverage, refinancing needs, balance-sheet liquidity.
- USD sensitivity: foreign revenue/cost exposure and FX sensitivity, but only if pre-event filings/valid metadata support it.
- Inflation/commodity sensitivity: input-cost intensity, energy/material exposure, pricing power/proxy margin stability.
- Labor sensitivity: labor cost intensity and labor-dependent business models.
- Cyclical demand and inventory sensitivity.
- Sector/industry as controls, not as a substitute for company exposure.

Each feature needs: exact formula; source; as-of/PIT rule; coverage; missingness; winsorization learned on training data only; minimum data thresholds; leakage tests. Do not use modern sector membership or company classification retrospectively without effective dates.

## 6. M2/M3 research design

- Event unit is unique macro event ID/date, not stock rows. Multiple reports sharing the same release session are not independent events.
- Primary dependent variable: stock total return less contemporaneous industry benchmark return; secondary excess SPY return. Adjusted for split/dividend consistently.
- Horizons: D1, D5, D10, D20 trading sessions. Fix entry convention per timestamp: premarket before regular open may enter same-day open only when precise verified time supports it; intraday/after-hours enter next eligible session open. Date-only events cannot enter exact intraday cohorts.
- Cross-sectional model: event-level interactions such as event surprise × pre-event stock exposure; event fixed effects / market and sector controls; report event-cluster bootstrap or two-way (event-date and ticker) inference; account for serial dependence and overlapping holding windows.
- Keep event-family hypotheses pre-registered. Apply BH or other stated multiplicity correction across the complete family of candidate interactions/horizons/subgroups.
- Explore/validate split chronologically by event date; all stocks within an event date must remain in one period. No random stock-row split.
- Test direction, magnitude, dispersion/volatility and ranking ability separately. Statistical significance is not sufficient: check stability, effect size, coverage and practical tradability.
- If event count is too small (particularly FOMC ~8/year), do not create pseudo-replication by multiplying by number of tickers.

## 7. M4/M5 strategy gate

Only after M1 data readiness and M3 robust cross-sectional signal:
- Convert pre-event exposure/surprise interaction into a daily ranked ticker shortlist.
- Entry next tradable session under conservative rules; holding 5–20 sessions; compare long-only first. No shorting/leverage/options by default.
- Include commissions, spread/slippage, market impact proxy, turnover and realistic capacity; user's earlier assumptions where relevant: IBKR Pro Tiered, USD 50,000 starting capital, but no IBKR connection or paper launch now.
- Risk controls: position cap, sector concentration, volatility scaling, max drawdown and turnover.
- Compare against risk-matched SPY/BIL and industry ETF/BIL baselines, not only SPY 100%.
- Walk-forward OOS with multiple market regimes, and report survivorship/PIT universe coverage. Existing OHLCV PIT feasibility problems remain a material dependency; do not quietly substitute current constituents.
- NO-GO if data provenance fails, sample too small, multiple-testing adjusted evidence fails, costs erase return, or OOS performance is not robust.

## 8. Immediate next tasks (strict order)

1. Inspect #445 full report/code and verify event inventory/audit artifacts; preserve it unmerged.
2. Check the existing merged #271 code and #282 study engine; create an explicit reuse-vs-rewrite table.
3. Inventory accessible public official sources for 2021–2026 BLS and current FOMC exact event data via approved methods; do not bypass 403, rotate proxies or spoof identity.
4. Audit whether event-level historical surprises can be sourced from genuinely timestamped consensus archives. If not, do not use actual-minus-consensus.
5. Design M1 event coverage schema plus issuer exposure source audit and coverage thresholds.
6. Build tests and a standalone research report on a new branch, branched from a verified current research base; no merge and no main writes.
7. Run focused tests then full Python 3.12 CI; report actual CI HEAD SHA and artifacts.
8. Only after the data gate is satisfied consider M2 exposure panels and M3 empirical cross-sectional study.

## 9. Non-negotiable boundaries

- No merges, no PR close as a cleanup shortcut, no main modification.
- No production scan/review/dashboard/score/risk/ledger/stop/order changes.
- No GitHub cron or automatic external workflow scheduling.
- No paid data purchase or VPS; free sources only, USD 20 cap.
- No IBKR connection, no live orders, no PAPER/Shadow launch, no portfolio deployment.
- No raw research data upload unless explicitly approved; generated manifests/reports may be committed on the research branch.
- Use Python 3.12 for the repo full test suite.
- Explicitly state partial coverage and DATA_BLOCKED; never fabricate consensus, initial values, exact publication time, or historical first-seen.

## 10. Audit references

- Main operating constraints: `docs/QUANT_LOW_FREQUENCY_OPERATIONS.md`
- Official macro feasibility report: PR #445 `docs/research/MACRO_EVENT_RESPONSE.md`
- Macro tool: `tools/research/macro_event_response.py`
- Macro tests: `tests/test_macro_event_response.py`
- P12.4 closeout branch: `research/p12-event-fundamental-feasibility`
