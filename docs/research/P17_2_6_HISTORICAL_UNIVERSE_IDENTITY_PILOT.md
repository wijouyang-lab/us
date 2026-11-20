# P17.2.6 Historical Universe Identity Pilot

Date: 2026-11-20
Branch: `research/p17-2-6-historical-universe-identity-pilot`
Base: `9b07f588dd5af05017d2d4cba36ae87a23d9460a`
Status: **DATA_BLOCKED (pilot not completed)**

## 1. Sample

From P13 aligned panel, exact anchor dates:

| anchor | date | expected members | sampled |
|---|---|---:|---:|
| A | 2020-06-30 | 499 | 100 |
| B | 2022-06-30 | 498 | 100 |
| C | 2024-06-28 | 489 | 100 |

```text
sampled ticker-date observations: 300
unique tickers: 258
```

Sampling was deterministic, stratified by price coverage, later listing and
removal status.

## 2. CIK candidates

Current SEC CompanyFacts ticker mapping:

| anchor | CIK candidates / 100 |
|---|---:|
| 2020-06-30 | 67 |
| 2022-06-30 | 76 |
| 2024-06-28 | 90 |
| total | 233 / 300 |

These are **current-only candidates**, not historical identity proof. The low
2020 count reflects delisted/renamed names missing from the current ticker map.

## 3. As-of evidence

Using only the 8 already-verified XBRL filing points:

```text
ASOF_EVIDENCE_AVAILABLE: 0
STALE_OR_UNCONFIRMED: 3
NO_ASOF_EVIDENCE: 297
```

No new 300-filing SEC retrieval was performed in this round. Therefore:

```text
VERIFIED_SECURITY_POINT for the 300 sample: 0
network requests: 0
```

This is not a SEC data failure finding; it is an incomplete extraction. The
pilot cannot pass the 80/100 verified security threshold.

## 4. Coverage conclusion

No anchor reaches:

- 80/100 verified original XBRL security points;
- 80/100 as-of evidence;
- the required conflict / leakage audit.

The only path that could change this is retrieving and parsing the historical
10-K/10-Q for the 300 samples, then re-running exact context pairing.

## 5. Decision

```text
P17_2_6_SAMPLE = PASS (300/300)
P17_2_6_CIK_CANDIDATES = 233/300
P17_2_6_VERIFIED_SECURITY_POINTS = 0/300
P17_2_6_ASOF_EVIDENCE = 0/300
P17_2_6_OVERALL = DATA_BLOCKED
```

The pilot does **not** support expanding to a full 2020–2024 quarterly identity
panel yet. It also does not prove SEC cannot support it; the required 300-filing
extraction was not completed.

## 6. Files

- `tools/research/p17_2_6_universe_identity_pilot.py`
- `tests/test_p17_2_6_universe_identity_pilot.py`
- `data/research/p17_2_6/p17_2_6_sample_manifest.csv`
- `p17_2_6_ticker_cik_candidates.csv`
- `p17_2_6_asof_evidence.csv`
- `p17_2_6_stale_evidence.csv`
- `p17_2_6_anchor_coverage.csv`
- `p17_2_6_price_member_join.csv`
- `p17_2_6_request_audit.csv`
- `p17_2_6_identity_conflicts.csv`
- `p17_2_6_summary.json`
- `p17_2_6_manifest.json`

No alpha, NAV, trade ledger, or production change.
