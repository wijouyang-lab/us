# Historical S&P 500 Constituent Coverage Audit

Date: 2026-10-29 UTC
Research only. Price panel unchanged.

## Sources reviewed

| Source | Range | Rows | License | Status |
|---|---|---:|---|---|
| chinobing/historical_sp500_constituents | 1996-01-02 .. 2026-10-29 | 3,928 snapshots | MIT | candidate |
| thuningxu/sp500nq100 | 1996-01-02 .. 2026-06-02 | 2,712 snapshots | **no repository license found** | candidate only; not used as primary |
| repo `sp500_components_history.csv` | 1957-03-04 .. 2026-10-06 | 1,005 events | provenance incomplete | identity cross-check only |

Both external sources are community compilations derived from Wikipedia change
tables, not S&P DJI official bulk data. Dates appear to be effective membership
dates, but only one event was checked against an official announcement.

Source URLs:

- https://github.com/chinobing/historical_sp500_constituents
- https://github.com/thuningxu/sp500nq100

## Official event cross-check

S&P DJI announcement dated 2024-09-06:

https://press.spglobal.com/2024-09-06-Palantir-Technologies,-Dell-Technologies,-and-Erie-Indemnity-Set-to-Join-S-P-500-Others-to-Join-S-P-MidCap-400-and-S-P-SmallCap-600

Effective before the open on **2024-09-23**:

- add PLTR, DELL, ERIE;
- remove AAL, ETSY, BIO.

Both chino and thun snapshots for 2024-09-23 match all six actions.

This validates one event, not the full history.

## Source agreement

Common snapshot dates: **2,709**.

| Metric | Value |
|---|---:|
| Jaccard mean | **0.934** |
| Jaccard min | **0.888** |
| Dates with Jaccard < 0.98 | **2,521** |

The two community sources disagree materially. They cannot both be treated as
canonical. Chino is used for the coverage audit because it has an explicit MIT
license and current through 2026-10-29; thun is a cross-check only.

## Yearly membership and price coverage

Using the chino snapshot at each year-end and the existing 503-name panel:

| Year | Constituents | In panel | Missing | Coverage |
|---|---:|---:|---:|---:|
| 2016 | 484 | 336 | 148 | 69.4% |
| 2017 | 491 | 353 | 138 | 71.9% |
| 2018 | 497 | 364 | 133 | 73.2% |
| 2019 | 499 | 384 | 115 | 77.0% |
| 2020 | 501 | 397 | 104 | 79.2% |
| 2021 | 501 | 407 | 94 | 81.2% |
| 2022 | 498 | 425 | 73 | 85.3% |
| 2023 | 503 | 445 | 58 | 88.5% |
| 2024 | 503 | 463 | 40 | 92.0% |
| 2025 | 501 | 478 | 23 | 95.4% |
| 2026 | 503 | 503 | 0 | 100% |

The rise is mechanical: the price panel is the **current 503-name universe**.
Historical removed names are progressively absent.

## Unique historical universe

- Unique historical tickers in chino: **705**
- Tickers present in current panel: **503**
- Historical tickers with no panel series: **202**
- Year-ticker missing rows: **926**
- Late panel starts (history first 鈮?016 and panel first >5 days later): **15**
  - all start at panel inception 2016-09-19, not a source gap.

Missing unique list:

`docs/research/historical_constituent_missing_unique_2026-10-29.csv`

Full yearly/ticker detail:

`docs/research/historical_constituent_2026-10-29_detail.csv`

## Identity risks

Repo event table has **971 unique symbols**, of which **13 have more than one
CIK**:

`AGN, CEG, DD, DELL, DOW, GGP, HLT, IR, MNST, NE, Q, SNDK, WM`

`Q` has 3 CIKs. Any historical membership row must be joined by CIK/date, not
ticker alone. The earlier ADCT/INFO probes showed ticker reuse directly.

## Free official-source check

SEC submissions (HTTP 200) confirm identity for sample names:

| Ticker | SEC name | Former name |
|---|---|---|
| ATVI | Activision Blizzard, Inc. | ACTIVISION INC /NY |
| ALXN | ALEXION PHARMACEUTICALS, INC. | ALEXION PHARMACEUTICALS INC |
| AAL | American Airlines Group Inc. | AMR CORP |

SEC provides identity/event evidence, **not OHLCV**. No price series was
created from SEC records.

## Data coverage change

```text
new constituent rows: 0
new price rows: 0
panel changed: no
```

This stage adds an audit, not delisted price coverage.

## Answers

1. **Can free historical membership be reconstructed reliably?**
   Partially. A candidate timeline is available, but community sources disagree
   materially and only one official event was verified. It is not official
   truth and cannot be promoted to canonical membership.

2. **How much of the real historical universe is covered?**
   503 of 705 unique historical tickers have a current-panel series; 202 do
   not. 2016 coverage is 336/484 (69.4%); 2026 is 503/503 by construction.

3. **Can a different public source provide verifiable pre-delisting OHLC?**
   No. SEC/S&P official material provides identity/events only. Yahoo/Wayback
   were already tested and failed. No new OHLC source was found.

4. **Which backtests are valid?**
   Current-universe exploratory backtests only. Historical-universe,
   delisted-inclusive, or full-PIT conclusions cannot be drawn.

## Artifacts

- yearly summary: `docs/research/historical_constituent_2026-10-29_yearly.csv`
- detail: `docs/research/historical_constituent_2026-10-29_detail.csv`
- missing: `docs/research/historical_constituent_2026-10-29_missing.csv`
- missing unique: `docs/research/historical_constituent_missing_unique_2026-10-29.csv`
- source comparison: `docs/research/historical_constituent_2026-10-29_source_comparison.json`
- code: `tools/research/historical_constituent_audit.py`
