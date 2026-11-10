# Final Identity Classification and Minimal Event Study

Date: 2026-10-29 UTC
Research only. No canonical write.

## 1. Final four

| Ticker | CIK | SEC name | Current ticker | Classification |
|---|---|---|---|---|
| PSKY | 0002041610 | Skydance Corp | SKYD | `TICKER_OR_NAME_CHANGED` |
| SOLS | 0002064953 | Solstice Advanced Materials Inc. | SOLS | `STILL_TRADING` |
| TAP | 0000024545 | Molson Coors Beverage Co. | TAP | `STILL_TRADING` |
| TTD | 0001671933 | Trade Desk, Inc. | TTD | `STILL_TRADING` |

Key facts:

- PSKY label maps to current SEC ticker `SKYD`; same CIK, former name
  `Paramount Skydance Corp` / `New Pluto Global, Inc.`. It is not a delisting.
- SOLS is a 2025 listing (`Solstice Advanced Materials`), after the panel
  start; no historical panel series is expected.
- TAP/Molson Coors and TTD/Trade Desk still have current SEC tickers; their
  absence is an index-membership gap, not delisting.
- PSKY/SOLS/TTD have short or remapped histories; this is not evidence of
  missing prior prices.

## 2. Final classification 鈥?202/202 reviewed

| Category | Count |
|---|---:|
| `DELISTED_OR_ACQUIRED` | **84** |
| `STILL_TRADING` | **81** |
| `TICKER_OR_NAME_CHANGED` | **34** |
| `TICKER_REUSE_SUSPECTED` | **2** |
| `IDENTITY_UNRESOLVED` | **1** |
| `HISTORICAL_MEMBERSHIP_ONLY` | **0** |
| Total | **202** |

Remaining `HISTORICAL_MEMBERSHIP_ONLY`: **0**.

The one unresolved is FRC; the two reuse suspects are INFO and STI.

## 3. Classification quality audit

Audit file:

`docs/research/classification_quality_audit_2026-10-29.csv`

Actual checks over all 202 records:

- 202 records, 0 duplicate tickers;
- 0 `no_sec_record` after adding the INFO/STI/SBNY special records;
- 0 current-still ticker incorrectly marked delisted;
- 0 dead/changed record with old ticker still current;
- 0 CIK mismatch against component CIK;
- 32 `DELISTED_OR_ACQUIRED` records have only `25-NSE` metadata and no
  `15-12G`: evidence status **`SEC_METADATA_ONLY_25NSE`**, lifecycle confidence
  **MEDIUM**;
- all records have `last_trade_status=NOT_INDEPENDENTLY_VERIFIED`;
- no duplicate successor ticker mapped to unrelated entities in the checked
  changed set; repeated successors `GEN` and `RVTY` are same-issuer cases.

### EQR and MMC recheck

| Old | Current | CIK | Former name evidence | Result |
|---|---|---|---|---|
| EQR | VMRK | 0000906107 | SEC former name `EQUITY RESIDENTIAL` (2002鈥?026) | mapping valid |
| MMC | MRSH | 0000062709 | SEC name Marsh & McLennan; current ticker MRSH | mapping valid |

`EQR -> VMRK` is not a name-similarity inference: the same CIK has former
name Equity Residential and current Vivmark Residential.

## 4. Minimal event study 鈥?Fed press releases / SPY

Data:

- Fed 2026 press releases: 114 exact-minute timestamps.
- Market proxy: SPY daily open/close through 2026-10-27.

Rules:

```text
event before open -> same session open
event at/after open -> next session open
+1/+5 = close of entry+1 / entry+5 sessions
round-trip cost = 2 x 5 bps
```

Actual results:

| Metric | Event sample | Unconditional SPY |
|---|---:|---:|
| events | 114 | 197 sessions |
| unique entry dates | **84** | 鈥?|
| mean gross +1 | +0.1007% | +0.0714% |
| mean net +1 | **+0.0007%** | 鈥?|
| mean gross +5 | +0.2145% | +0.2850% |
| mean net +5 | **+0.1145%** | 鈥?|

Interpretation:

- +1 gross is slightly above unconditional, but after 10 bps round-trip it is
  essentially zero.
- +5 gross is below unconditional; net is +0.11% but not evidence of alpha.
- 114 events collapse to 84 unique entry dates; windows overlap.
- This is a **retrospective counterfactual**, not PIT: no historical
  `first_seen_at`; Fed timestamps are publication times, not system capture.
- No statistical significance or deployable conclusion is claimed.

## 5. Data and research boundary

- No new price data downloaded this round.
- No canonical writes.
- No production changes.
- MarketParquet/ADG/Stooq/Nasdaq routes were not retried.
- Event study uses SPY as a market proxy and existing Fed public-domain
  timestamps; it is a feasibility study, not an alpha claim.

## 6. Tests

- Final classification tests: 16 in `test_missing_reason_classifier.py`.
- Event study tests: 2 in `test_fed_event_study.py`.
- Fixed-five OOS tests: 5.
- Source audit tests: 4.

Full CI is reported after commit.

## 7. Artifacts

- final v10: `docs/research/missing_202_reason_classification_v10_2026-10-29.csv`
- quality audit: `docs/research/classification_quality_audit_2026-10-29.csv`
- special SEC: `docs/research/missing_202_special_sec_2026-10-29.json`
- event study: `docs/research/fed_event_study_2026-10-29.json`
- event detail: `docs/research/fed_event_study_2026-10-29_events.csv`
- event tool: `tools/research/fed_event_study.py`
