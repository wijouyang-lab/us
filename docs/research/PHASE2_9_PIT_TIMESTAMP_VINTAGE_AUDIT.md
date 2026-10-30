# Phase 2.9 PIT Timestamp and Macro Vintage Audit

Date: 2026-10-30
Label: `EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED`
No production changes. No validated alpha.

## 1. SEC: acceptance vs first public

Fields are now explicitly separated:

```text
acceptanceDateTime = EDGAR receipt time
filing_date         = filing date
first_public_at     = first public visibility (not proven)
market_usable_at    = earliest defensible decision time
```

`acceptanceDateTime` is **not** treated as first-public.

Actual 50-company audit:

| Metric | Result |
|---|---:|
| Requested current-panel issuers | 50 |
| submissions HTTP 200 | 50 |
| issuers with recent 10-Q/10-K/8-K | 50 |
| recent filings with acceptance time | 781 |
| first-public verified | **0** |
| strict PIT events | **0** |

CIK mapping from the local S&P components table:

```text
current price tickers: 503
current tickers mapped to CIK: 501
```

This is still the current 503-name universe; it is not a historical PIT universe.

### What the official sources show

- submissions JSON: acceptanceDateTime exists, but no first-public field;
- filing detail/index/header: not independently verified in this environment;
- no first-public evidence in the sample.

Therefore every SEC event keeps:

```text
first_public_at = null
timestamp_confidence = unverified
pit_eligible = false
```

## 2. Macro vintage audit

Requested series:

```text
FEDFUNDS, DGS2, DGS10, CPIAUCSL, CPILFESL,
PCEPI, PCEPILFE, UNRATE, PAYEMS, ICSA
```

Actual environment:

```text
FRED_API_KEY present: false
ALFRED_API_KEY present: false
```

Endpoint results:

| Endpoint | Result |
|---|---|
| `api.stlouisfed.org/fred/series/observations` without key | HTTP **400** (missing API key) |
| `fred.stlouisfed.org/graph/fredgraph.csv` | **ReadTimeout** |
| `alfred.stlouisfed.org/graph/fredgraph.csv?vintage_date=...` | **ReadTimeout** |

No key was printed or committed. No response was fabricated.

### Vintage status

| Requirement | Status |
|---|---|
| Historical vintage | UNAVAILABLE |
| First-release value | UNAVAILABLE |
| Revision history | UNAVAILABLE |
| Exact release timestamp | UNAVAILABLE |
| `vintage_verified` | false |
| `pit_eligible` | false |

Current FRED values cannot be substituted for first-release values.

## 3. Time alignment rules

- Before close: only if exact public time is verified and decision time is after it.
- During session: exact time required; earliest decision time explicit.
- After close: next trading session.
- Non-trading day: next trading session.
- Unknown time: excluded from strict PIT.

Tests cover before/after close, non-trading, and unverified first-public.

## 4. Tests

`tests/test_pit_timestamp_audit.py`: 5 passed
`tests/test_macro_vintage_audit.py`: 3 passed

Coverage:

- acceptance != first-public;
- unverified first-public not PIT;
- after-close/non-trading rules;
- first-release vs revised value separation;
- missing vintage not verified;
- no API key printed;
- empty macro data not filled.

Full CI after commit.

## 5. Strict PIT count

```text
SEC events with verified first-public: 0
SEC events PIT-eligible: 0
Macro series with verified vintage: 0
Macro observations PIT-eligible: 0
```

## 6. Remaining gaps

- no official first-public timestamp;
- no filing-detail/header evidence in this environment;
- no FRED/ALFRED key; no vintage;
- no historical news archive;
- no analyst expectations;
- no delisted-security events;
- current 503-name survivorship bias.

## 7. Conclusion

The data sources do **not** currently support strict PIT SEC or macro event
research. Acceptance metadata remains useful for descriptive filing studies only.
No event or macro factor is admitted to PIT.

## 8. Artifacts

- `tools/research/pit_timestamp_audit.py`
- `tools/research/macro_vintage_audit.py`
- `tests/test_pit_timestamp_audit.py`
- `tests/test_macro_vintage_audit.py`
- `docs/research/sec_cik_timestamp_coverage_2026-10-30.json`
- `docs/research/macro_vintage_audit_2026-10-30.json`
