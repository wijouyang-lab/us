# SEC Primary-Source Evidence — P4.3

Date: 2026-11-04
Branch: `research/dividend-primary-source-p43`
Stacked target: `research/dividend-quality-p42-evidence-closure`
Status: **primary documents fetched; 0 SPLIT_CONFIRMED; 0 dividend events VERIFIED**

## 1. What was actually downloaded

- SEC Archives index + primary document for **22/22** split-fact accessions.
- Download failures: **0**.
- Documents downloaded per split record: 1 primary document.
- Full filing bodies are cached locally under `data/sec/filings_p43/`; only
  hashes, URLs, short excerpts and metadata are committed.

No full filing text was copied into GitHub.

## 2. Split evidence result

For the 22 P4.2 conversion facts:

| Result | Count |
|---|---:|
| accession found and primary downloaded | 22 |
| split ratio + effective date confirmed | **0** |
| PARTIALLY_VERIFIED | **22** |
| CONFIRMED | **0** |

Why:

- the primary documents are 8-K/10-K/10-Q filings, but the XBRL accession often
  points to a filing that only contains the split fact, not an explicit
  "effective date" sentence;
- example: AAPL's 2015 8-K (accession `0001193125-15-023732`) contains no
  split text; it cannot confirm the 7:1 event;
- XBRL `fact end` was not used as `effective_date`;
- no filing date was used as a split effective date.

Therefore P4.2's conservative status is preserved, not promoted.

## 3. DPS share basis

- 0 companies have a proven `AS_DECLARED_AT_TIME` history.
- 0 companies have a proven `SPLIT_ADJUSTED` history.
- 28/28 remain `DPS_SPLIT_BASIS_UNVERIFIED`.
- No DPS CAGR, consecutive growth, cut count or volatility is used in scoring.

`adjust_dps()` still refuses `UNKNOWN`/`CONFLICTED`, and does not double-adjust
`SPLIT_ADJUSTED`.

## 4. SEC 8-K dividend-event scan

Scope: the 22 `DIVIDEND_PAYER` companies, last 24 months, SEC Submissions 8-Ks.

Actual counts:

| Metric | Count |
|---|---:|
| companies | 22 |
| 8-K filings seen | 581 |
| primary documents downloaded | 110 |
| download failures | 0 |
| relevant 8-K by keyword | 11 |
| candidate events | 3 |
| VERIFIED | **0** |
| PARTIALLY_VERIFIED | **3** |
| CONFLICTED | 0 |

Candidate tickers:

```text
CAT  $1.51
BAC  $0.32
NEE  $67.75
```

These are **candidates only**:

- filing date is used as announcement date;
- no official ex-date, record date or payment date was parsed;
- NEE's amount is an outlier and may be a preferred/other distribution;
- no candidate is marked VERIFIED.

Annual DPS declines are still not events.

## 5. Event status meanings

The collector distinguishes:

```text
FETCH_NOT_IMPLEMENTED
FETCH_FAILED
NO_MATCHING_FILING
NO_EVENT_EVIDENCE_IN_FETCHED_FILINGS
EVENT_CANDIDATES_FOUND
```

Current status:

```text
EVENT_CANDIDATES_FOUND
```

It does **not** mean 3 verified dividend declarations.

## 6. P4.1 score impact

P4.3 did not raise any score:

| Status | Count |
|---|---:|
| SCORE_READY | **10** |
| NOT_READY | **18** |

The same 10 companies remain: AAPL, MSFT, NVDA, HD, MCD, NKE, CAT, HON, UNP,
CVX. No DPS growth component was added because split basis is still unverified.

## 7. SEC request behavior

- `SEC_USER_AGENT` is required by the fetcher.
- Placeholder UA is rejected unless `ALLOW_SEC_PLACEHOLDER=1` is explicitly set
  for this audit run.
- Request interval >= 0.25s.
- 403/404/429 are returned as distinct HTTP statuses in fetch results.
- Cache hit does not re-request the file.
- SHA-256 is stored for each downloaded document.
- Failure is not converted into an empty successful result.

The audit run used a local placeholder contact because no real SEC contact is
configured. This is **not** a production-ready SEC identity; production must set
a real contact.

## 8. Files

```text
tools/investment_research/dividend/sec_filing_fetcher.py
tools/investment_research/dividend/dividend_event_collector.py
tools/investment_research/dividend/dividend_quality_report_p43.py

data/research/split_evidence_p43.json
data/research/dividend_events_p43.json
data/research/dividend_quality_p43.json

tests/test_primary_sources_p43.py
```

## 9. Remaining

1. Split effective dates still need explicit official text; XBRL alone is not
   enough.
2. No verified DPS share basis.
3. No verified DECLARED/EX/PAYMENT events.
4. Candidate events need date/amount cross-check against 8-K Exhibit 99.1 or IR.
5. NEE candidate amount must be resolved, not counted as common dividend.
6. Real SEC contact must be configured for production fetches.

No production scan/trade code was modified. No Yahoo/AKShare/Finnhub was used.
