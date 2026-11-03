# Historical PIT Universe & Delisted OHLCV Feasibility

Date: 2026-11-04
Branch: `research/pit-universe-data-feasibility`
Status: **NO-GO for formal data-layer development; one price source passes partially**

Research only. No production changes, no broker, no orders.

## 1. Decision first

A free, delisted-inclusive S&P 500 price panel exists and is usable for a
20-ticker trial. However, the full formal data layer **fails** the agreed
acceptance gates:

| Gate | Result |
|---|---|
| 10 years of history | FINSABER 2000-2024: yes |
| 3-year untouched holdout | no; 2025-2026 absent |
| Member-day coverage >=95% | **not computable**; no full PIT membership after 2019 |
| Historical ticker coverage >=98% | **93/98 = 94.9%** |
| Delisted OHLCV obtained | 93/98; 20/20 sample; one sample anomaly |
| Corporate actions with source | **no split/dividend fields**; unverified |
| No future leakage | not yet proven at full-universe level |
| Reproducible raw data | SHA-256 yes; full 265 MB payload not committed |

Therefore: **do not build the formal multi-table data layer yet.**
FINSABER is retained as a price-source candidate, not accepted as a production
data layer.

## 2. Historical membership source

Source tested:

```text
https://raw.githubusercontent.com/fja05680/sp500/master/
S%26P%20500%20Historical%20Components%20%26%20Changes.csv
```

Actual result:

- HTTP 200;
- 7,791,584 bytes;
- 2,595 daily snapshot rows;
- date range **1996-01-02 to 2019-01-11**.

This is a useful historical membership source for 1996-2019, but it **stops in
January 2019**, so it cannot support 2020-2024 membership or a 3-year holdout.
No second free membership source was accepted in this round.

The existing 98-ticker identity audit has CIK, company name, membership added
and removed dates for all 98, but that is a failure-set sample, not a complete
constituent history. It cannot be used to compute member-day coverage for the
whole index.

## 3. Price source trial

### FINSABER free dataset (Hugging Face, Apache-2.0)

```text
https://huggingface.co/datasets/finsaber-team/FINSABER-reproduce/
data/price/all_sp500_prices_2000_2024_delisted_include.csv
```

Actual download:

- HTTP 200;
- 265,180,873 bytes;
- 2000-01-03 to 2024-12-31;
- fields: date, open, high, low, close, adjusted_close, volume, symbol;
- contains delisted symbols;
- no split/dividend records;
- upstream price provenance is not independently documented; this is a
  redistributed research dataset, not an exchange feed.

A 20-ticker sample was extracted and stored with SHA-256.

## 4. 20-ticker real test

Sample chosen from the existing identity audit, not by download convenience:

| Group | Tickers |
|---|---|
| Delisted | ABMD, AET, AGN, ALXN, ATVI, CELG, CERN, XLNX |
| Merger | DISCA, DWDP, ESRX, MYL |
| Ticker change | FB, ANTM, PARA, TWTR |
| Current | AAPL, MSFT, JPM, XOM |

Actual coverage: **20/20 symbols found**.

| Ticker | Rows | First | Last | Last close | Note |
|---|---:|---|---|---:|---|
| ABMD | 5,781 | 2000-01-03 | 2022-12-23 | 381.02 | J&J acquisition |
| AET | 4,758 | 2000-01-03 | 2018-11-28 | 212.70 | CVS acquisition |
| AGN | 5,120 | 2000-01-03 | 2020-05-08 | 193.02 | AbbVie acquisition |
| ALXN | 5,422 | 2000-01-03 | 2021-07-21 | 182.50 | AstraZeneca acquisition |
| ATVI | 5,984 | 2000-01-03 | 2023-10-13 | 94.42 | Microsoft acquisition |
| CELG | 5,004 | 2000-01-03 | 2019-11-20 | 108.24 | BMS acquisition |
| CERN | 5,645 | 2000-01-03 | 2022-06-08 | 94.92 | Oracle acquisition |
| XLNX | 5,568 | 2000-01-03 | 2022-02-16 | 194.92 | AMD acquisition |
| DISCA | 4,221 | 2005-07-06 | 2022-04-08 | 24.43 | WBD merger |
| DWDP | 4,886 | 2000-01-03 | 2019-06-28 | 30.52 | DowDuPont split |
| ESRX | 4,773 | 2000-01-03 | 2018-12-20 | 92.33 | Cigna acquisition |
| **MYL** | 5,255 | 2000-01-03 | 2020-11-18 | **0.079** | **anomaly: 99.5% one-day drop on 2020-11-17; unusable last close** |
| FB | 2,543 | 2012-05-18 | 2022-06-27 | 169.49 | META ticker change |
| ANTM | 5,200 | 2001-10-30 | 2022-06-27 | 482.58 | ELV ticker change |
| PARA | 6,289 | 2000-01-03 | 2024-12-31 | 10.46 | current / renamed |
| TWTR | 2,259 | 2013-11-07 | 2022-10-27 | 53.70 | Musk take-private |
| AAPL | 6,289 | 2000-01-03 | 2024-12-31 | 250.42 | current |
| MSFT | 6,289 | 2000-01-03 | 2024-12-31 | 421.50 | current |
| JPM | 6,289 | 2000-01-03 | 2024-12-31 | 239.71 | current |
| XOM | 6,289 | 2000-01-03 | 2024-12-31 | 107.57 | current |

Success count: **20/20 found**; usable without anomaly: **19/20**.
Failure/quality count: **1/20** (MYL).

MYL shows exactly why ticker-string joins are unsafe: the final two rows are
$0.079 with normal volume, likely a ticker/security reuse or corporate-action
artifact. It is excluded from any return use pending identity verification.

## 5. Other free sources actually tested

20-ticker requests; counts are successful responses with plausible rows, not
just HTTP 200.

| Source | Free | Key | Delisted support | Actual 20-ticker success | Verdict |
|---|---|---:|---|---:|---|
| FINSABER HF CSV | yes | no | yes | **20/20** | candidate only |
| EODHD `demo` | demo only | demo token | no | 2/20 (current only) | rejected |
| Twelve Data `demo` | demo only | demo key | no | 1/20 | rejected |
| Nasdaq public API | yes | no | no | 5/20 (current only) | rejected |
| fja05680 membership CSV | yes | no | n/a (membership only) | 1996-2019 only | insufficient history |

Previously tested and not re-tested:
Yahoo/yfinance (not independent), Stooq (JS challenge), Nasdaq (already),
Internet Archive, SEC EDGAR (no OHLCV), OpenBB Yahoo provider (not independent).

Raw request statuses: `data/research/pit_data/source_trials_20.json`.

## 6. 98-ticker status

`data/research/pit_data/ticker_status_98_2026-11-04.csv` merges the existing
identity audit with actual FINSABER coverage.

- 98 identity records;
- **93 found** in FINSABER;
- **5 missing**:
  - DAY (event 2026-02-09, outside 2024 cutoff);
  - TSO (Andeavor; acquired 2017);
  - UA.C (class suffix);
  - WYN (renamed Travel + Leisure);
  - YHOO (Altaba).
- Historical ticker coverage: **93/98 = 94.9%**, below the 98% gate.

Some found symbols have anomalies (ACS last close 0.095; MYL 0.079), so raw
coverage is not the same as usable coverage.

## 7. PIT and corporate-action audit

- `adjusted_close` is present, but split and dividend records are absent.
- There is no way to reconstruct raw + adjusted independently from this file.
- Membership announcement vs effective date cannot be validated beyond the
  identity audit's existing fields; the full 2020-2024 membership history is
  missing.
- No future-data injection test has been run at full-universe level.
- The 3-year untouched holdout cannot be formed because prices end 2024-12-31
  and the current period 2025-2026 is absent.

## 8. Proposed layer design (not built)

Only after the gates pass:

```text
security_master(security_id, cik, company_name, security_type)
ticker_history(ticker, security_id, start_date, end_date, source)
historical_index_membership(index, security_id, announcement_date,
                            effective_date, removal_date, source)
daily_ohlcv_raw(date, security_id, open, high, low, close, volume)
corporate_actions(security_id, action_type, announcement_date,
                  effective_date, value, source)
data_provenance(source, fetched_at, file, sha256, version)
```

Rules:

- raw and adjusted prices stored separately;
- no overwrite of raw files;
- no cross-source splice without reconciliation;
- no forward-fill/interpolation;
- ticker changes resolved through `security_id`, not string joins;
- announcement and effective dates separate.

No schema code was added because the data gates did not pass.

## 9. Stop decision

**NO-GO for formal data-layer development now.**

Reasons:

1. Full PIT membership after 2019 is missing.
2. Ticker coverage 94.9% < 98%.
3. Corporate actions are not independently sourced.
4. Price source provenance is a redistributed dataset, not an exchange feed.
5. No 2025-2026 data, so no 3-year holdout.
6. MYL/ACS-type ticker anomalies prove identity resolution is incomplete.

Do not recover factor research yet. Do not build an empty data layer.

## 10. Conditions to resume

1. A complete 2020-2024 (and current) historical S&P 500 membership source with
   announcement and effective dates.
2. Civil/legal license for delisted-inclusive OHLCV with documented upstream
   provenance.
3. Split/dividend records and a raw/adjusted reconciliation.
4. Ticker coverage >=98% and member-day coverage >=95%, with anomaly exclusions
   explicitly reported.
5. 10 years + 3-year untouched holdout, with no 2025-2026 leakage.
6. A reproducible SHA-256 manifest and independent source cross-check.

## 11. Artifacts

```text
data/research/pit_data/finsaber_20.csv
data/research/pit_data/sp500_membership_raw.csv
data/research/pit_data/source_trials_20.json
data/research/pit_data/ticker_status_98_2026-11-04.csv
data/research/pit_data/missing_tickers_identity_2026-10-28.csv
data/research/pit_data/manifest.json
tools/research/pit_data_feasibility.py
tests/test_pit_data_feasibility.py
```


---

# Addendum: 2019-2024 membership and validation (2026-11-04)

This addendum supersedes the earlier statement that 2019-2024 membership is
entirely unavailable.

## A. Membership source tests

### chinobing

- repo: chinobing/historical_sp500_constituents
- sp_500_historical_components.csv: 3,933 daily/change snapshots, 1996-01-02..2026-11-03
- sp500_changes_since_1996.csv: 703 change rows
- generator sp500.py fetches **Wikipedia current constituents** and appends to
  the stored historical CSV; it does not independently reconstruct 2019-2024
  from official S&P announcements
- verdict: useful for 2019-2024 sequence, but **Wikipedia-derived**, not
  independent; announcement vs effective dates unavailable.

### sp500-scraper / iShares

- repo: 
iazarbi/sp500-scraper
- 1,211 daily iShares CSVs available
- 70 month-end snapshots successfully fetched for 2019-2024
- 35,294 equity constituent rows
- fields: symbol, name, CUSIP, ISIN, asset_class
- verdict: independent of Wikipedia; month-end snapshot only, not official daily
  membership or announcement dates.

### SEC N-PORT

- SPY trust CIK 884394
- 2024-09-30 NPORT-P fetched (filed 2024-11-25), 504 holdings
- unique CUSIP: 479
- iShares 2024-09-30: 485 CUSIP
- overlap: **477**
- NPORT-only: 2; iShares-only: 8
- verdict: independent month-end cross-check, not daily membership; older
  2019-2023 NPORT parsing was not completed (XML format issues).

## B. Membership agreement

70 month-end common snapshots:

| Metric | Value |
|---|---:|
| Mean Jaccard | **99.19%** |
| Exact months | 18 / 70 |
| Worst Jaccard | 97.83% |

This is strong agreement and supports the 2019-2024 edge sequence, but it does
not provide official announcement dates or daily effective dates.

## C. Price coverage recomputation

Using iShares 2019-2024 equity member-months:

`	ext
member-month rows: 35,294
found in FINSABER on same month-end date: 34,818
member-month price coverage: 98.65%
`

This passes the 95% *month-end* coverage threshold.

98-ticker failure set:

`	ext
raw ticker presence: 93/98 = 94.9%
`

The 98% ticker gate still fails. Five missing: DAY, TSO, UA.C, WYN, YHOO.
MYL and ACS show severe last-price anomalies; raw presence is not valid identity
coverage.

## D. Corporate actions: 20 samples

corporate_action_samples_20.csv covers splits, dividends, mergers, ticker
changes, take-private and delisting.

Result:

- 20/20 events observed in FINSABER;
- **0/20 independently verified** against SEC/issuer documents in this round;
- FINSABER provides no split/dividend table, only raw and adjusted close;
- AAPL 2020-08-31 shows adjusted factor jumping from 0.2438 to 0.9751 across a
  4:1 split, which is not a stable split-adjusted factor. This must be treated
  as a corporate-action consistency failure, not accepted silently.

Therefore corporate-action coverage remains **UNVERIFIED** and the gate fails.

## E. FINSABER provenance / license

- Hugging Face dataset card says Apache-2.0.
- FINSABER code contains an **FMP** SP500 price downloader
  (llm_traders/finagent/configs/downloader/prices/fmp_day_prices_sp500.py).
- No upstream FMP redistribution grant is documented on the dataset card.
- Therefore: **PROVENANCE_UNVERIFIED**; Apache-2.0 on the aggregation does not
  prove rights to redistribute the underlying FMP prices.

## F. Revised gate result

| Gate | Result |
|---|---|
| 10 years | yes (2000-2024) |
| 3-year untouched holdout | **no** (2025-2026 absent) |
| Member-day coverage >=95% | month-end proxy 98.65%; daily not proven |
| Ticker coverage >=98% | **no, 94.9%** |
| Delisted OHLCV | found 93/98, but anomalies |
| Corporate actions verified | **no, 0/20 independent** |
| Provenance | **PROVENANCE_UNVERIFIED (FMP upstream)** |
| No future leakage at full-universe level | not proven |

Final decision remains **DATA_BLOCKED / NO-GO**. Do not build the formal data
layer.

## G. New artifacts

`	ext
data/research/pit_data/chinobing_sp500_changes_since_1996.csv
data/research/pit_data/chinobing_sp_500_historical_components.csv
data/research/pit_data/chinobing_sp500.py
data/research/pit_data/ishares_monthly_2019_2024.csv
data/research/pit_data/membership_diff_ishares_chinobing.csv
data/research/pit_data/nport_spy_20241125.xml
data/research/pit_data/nport_spy_2019_2024.csv
data/research/pit_data/corporate_action_samples_20.csv
data/research/pit_data/coverage_audit_2026-11-04.json
`
