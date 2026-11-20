# P17.2.4 SEC Identity History Audit

Date: 2026-11-20
Branch: `research/p17-2-4-sec-identity-history-audit`
Base: `9b07f588dd5af05017d2d4cba36ae87a23d9460a`
Status: **DATA_BLOCKED / PARTIAL_COVERAGE_ONLY**

## 1. P17.2.3 field conflicts

Raw SEC submission headers were treated as canonical; the P17.2.3 report
transcription was wrong in three places:

| accession | field | report | header / canonical |
|---|---|---|---|
| 000075330823000019 | acceptance | 16:06:40 | **2023-02-17 16:25:38** |
| 000104581022000079 | acceptance | 2022-05-26 16:30:23 | **2022-05-27 16:21:55** |
| 000104581024000316 | filed date | 2024-11-21 | **2024-11-20** |

CSV and Master Index agree with the raw headers.

## 2. Request count truth

P17.2.3's `request_audit.csv` now shows all 23 rows as cache hits because the
files were already local. The original first-run network count is **not
recoverable** from the current audit trail:

```text
ORIGINAL_NETWORK_REQUEST_COUNT_UNVERIFIABLE
current rows: 23 CACHE_HIT
network requests this round: 0
```

No files were re-downloaded to manufacture a network count.

## 3. Issuer vs security

Issuer level:

```text
8/8 accessions verified issuer filing points
```

Security level:

```text
16 facts total
VERIFIED_SECURITY_TICKER_POINT: 8 facts, 4 unique tickers
IDENTITY_CONFLICT: 8 facts, 5 unique tickers
```

Verified common tickers: **AAPL, NEE, NVDA, GOOGL**.

Conflicts:

- NEE.PRO / NEE.PRP / NEE.PRQ / NEE.PRR: the filing's `Security12bTitle` says
  "Common Stock, $0.01 Par Value" for all four preferred labels. No separate
  preferred security title/class context was captured. Cannot verify.
- GOOG: filing title says "Class A Common Stock" for both GOOG and GOOGL.
  GOOG is Class C; the title/class does not support GOOG as Class C. Cannot
  verify.

These are security-class conflicts, not CIK conflicts.

## 4. 75 accession audit

```text
75 accessions
2020–2024: 8
2014–2018: 6
2025: 2
2026: 59
metadata complete: 2/75
```

The 75 figure is not a 75-stock historical sample.

## 5. Daily cross-section

Only 8 filing dates have point observations. Daily verified securities:

```text
max 1 per observed filing date
gate 100 names: FALSE
```

No ffill between filing dates. No `VERIFIED_INTERVAL` was created.

P13 expected member-days: 633,971. Verified identity × price member-days: 0.

## 6. Decision

```text
P17_2_4_OVERALL = DATA_BLOCKED
P17_2_4_IDENTITY_PANEL = PARTIAL_COVERAGE_ONLY
P17_2_4_VERIFIED_INTERVALS = 0
P17_2_4_PIT_READY = FALSE
```

Reasons:

1. only 8 filing points;
2. only 4 verified common tickers;
3. 8 security-class conflicts;
4. no complete identity intervals;
5. max daily cross-section 1, far below 100;
6. 73/75 accessions lack metadata.

This free-SEC route can recover issuer filing metadata, but it cannot yet build
a historical security identity panel suitable for PIT factor research.

## 7. What would be needed

- security-level title/class facts for preferred and multiple share classes;
- explicit validity intervals, not filing points;
- coverage across most P13 member-days;
- a daily cross-section of at least 100 verified securities on 80% of signal
  days.

Until then: no PIT fundamental alpha.

## 8. Files

- `tools/research/p17_2_4_identity_history_audit.py`
- `tests/test_p17_2_4_identity_history_audit.py`
- `data/research/p17_2_4/p17_2_4_source_reconciliation.csv`
- `p17_2_4_field_conflicts.csv`
- `p17_2_4_request_provenance.csv`
- `p17_2_4_issuer_identity.csv`
- `p17_2_4_security_identity.csv`
- `p17_2_4_ticker_security_mapping.csv`
- `p17_2_4_identity_point_observations.csv`
- `p17_2_4_identity_intervals.csv`
- `p17_2_4_identity_conflicts.csv`
- `p17_2_4_75_accession_audit.csv`
- `p17_2_4_yearly_coverage.csv`
- `p17_2_4_quarterly_coverage.csv`
- `p17_2_4_daily_member_coverage.csv`
- `p17_2_4_cross_section_summary.json`
- `p17_2_4_summary.json`
- `p17_2_4_manifest.json`

No alpha, NAV, trade ledger, or production change.
