# Pre-Registered Event Study Proposal (No Results)

Date: 2026-10-28
Status: proposal only. Not executed. No alpha claim.

## Why no result yet

- 35 real Fed events exist.
- Price panel updated through 2026-10-27.
- First-seen is 2026-10-28.
- There is no post-first-seen trading bar yet.
- Strict PIT sample = 0.
- Publication-forward candidates = 35, pending price bars after availability.

## Hypothesis

Fed policy/central-bank publications have a short-horizon market reaction that
is not fully explained by same-day market beta.

This is a **publication-forward** study, not an exact event-time study because
`event_time` is absent for the RSS records.

## Event sample

- Sources: Federal Reserve press and speeches RSS only.
- Event types: `policy`, `central_bank`.
- Sample starts with the real archive and accumulates forward.
- Minimum 200 events across at least 12 UTC months before any primary test.
- No BLS/SEC data unless real contact credentials exist.
- Corporate/company events are out of scope.

## Availability and decision

- `available_at = max(source_published_at, first_seen_at, update_first_seen_at)`.
- Only the version known at the decision time is used.
- Decision timestamp is the close of the first trading bar strictly after
  `available_at`.
- Entry is the next executable close after the decision bar; exit at +1 and +5
  trading days.
- After-close/non-trading events use the next session, never the same-day close.
- No `event_time` is imputed.

## Market and returns

- Primary market series: equal-weight current panel as a proxy, clearly labeled
  current-universe/survivorship-biased.
- Secondary: no claim until a PIT market benchmark is available.
- Returns: close-to-close, raw OHLCV panel.
- Costs: 5 bps one-way base; 10/20 bps sensitivity.
- No adjusted-price field exists in the current panel; raw-close basis must be
  stated in every result.

## Dependence and overlap

- Multiple events on the same UTC day are one cluster for inference.
- Overlapping +1/+5 windows are clustered by event date.
- Block bootstrap by UTC date; no independent-event assumption.
- Deduplicate identical event IDs/versions.

## Out-of-sample

- Events observed before the preregistration date cannot be used as a
  retrospective PIT test unless their first-seen and price bars are valid.
- Primary evaluation starts after the first date with both:
  valid event observations and post-availability price bars.
- No tuning on the evaluation period.

## Multiple testing

- One primary hypothesis: 5-day market reaction.
- Secondary: 1-day reaction.
- BH correction over the two horizons.
- Any subgroup (policy vs central bank) is exploratory and reported separately.

## Stop rules

Stop and report no result if:

- fewer than 200 events or 12 months of forward coverage;
- strict/availability-valid events cannot be matched to post-availability bars;
- price coverage or timestamp integrity fails;
- costs eliminate the measured effect;
- result is explained by market beta.

Do not promote to production under any outcome.
