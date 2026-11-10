# AKShare US Daily Assessment

Date: 2026-10-29 UTC
Research only. No canonical panel writes.

## Environment and method

- Python 3.12.14
- AKShare **1.20.2** (installed for read-only evaluation)
- function: `akshare.stock_us_daily`
- source: Sina Finance staticdata `https://finance.sina.com.cn/staticdata/us/{symbol}`
- adjustment: `""` (raw), `qfq`, `qfq-factor`
- no login/token; AKShare is a wrapper, data is fetched from Sina.
- `stock_us_daily` has **no date-range parameter**; it fetches the full history.

Real commands:

```python
ak.stock_us_daily("HUBB", "")
ak.stock_us_daily("HUBB", "qfq")
ak.stock_us_daily("HUBB", "qfq-factor")
```

## HUBB 2026-10-28

| Field | Raw | QFQ |
|---|---:|---:|
| open | 444.68 | 444.68 |
| high | 444.805 | 444.805 |
| low | 426.91 | 426.91 |
| close | **437.33** | **437.33** |
| volume | 1,163,782 | 1,163,782 |

Validations:

- exact date match;
- `Low <= min(Open, Close)`;
- `max(Open, Close) <= High`;
- volume > 0;
- no duplicate date;
- raw and qfq identical on this date (no recent factor change).

QFQ factor table ends at 1985-08-12 (factor 0.5) and 1981-02-11; there is no
recent factor event around 2026-10-28.

Comparison:

| Source | 10/28 close | Volume |
|---|---:|---:|
| AKShare/Sina | 437.33 | 1,163,782 |
| Nasdaq | 437.33 | 1,163,860 |
| Yahoo chart | null (meta 437.33) | 1,163,816 |

AKShare supplies a valid raw row and a qfq-transformed row, but **no explicit
`Adj_Close` field**. `qfq` values must be treated as adjusted OHLCV, not renamed
to `Adj_Close`.

## 503-ticker coverage

Using the current panel's 503 tickers and the raw Sina endpoint:

```text
requested: 503
valid 2026-10-28 rows: 503
missing/empty: 0
invalid OHLCV: 0
duplicate tickers: 0
HTTP 200: 503
```

Two tickers initially failed because Sina uses dot symbols:

- `BF-B` -> `BF.B`
- `BRK-B` -> `BRK.B`

After alias resolution, 503/503 are present. Minimum history length is 17 rows
(recent listing), maximum 13,101.

Raw response hashes are in:

- `docs/research/akshare_2026-10-28/sina_raw.js`
- `docs/research/akshare_2026-10-28/sina_qfq.js`
- `docs/research/akshare_503_coverage_2026-10-28.csv`

## Comparison to the existing panel

Against the 502 panel rows present on 10/28:

```text
overlap: 502
max abs close difference: $0.005
mean abs close difference: $0.000014
close differences > $0.01: 0
volume: provider differs, not identical (consolidated vs vendor aggregation)
```

Data-quality correction found during comparison:

- AOS 10/28 had been written with the previous session's row (close 62.06,
  volume 1,185,400).
- The verified 10/28 row is open 62.60, high 62.60, low 60.47, close 60.86,
  volume 2,549,200.
- The local 10/28 increment was corrected; this is **not** a HUBB fill and does
  not change the HUBB missing status.

## Adjustment and revision semantics

- `raw`: no adjustment.
- `qfq`: Sina front-adjusted using the qfq factor table.
- `qfq-factor`: factors/adjustment values, not a price series.
- no provider update timestamp, revision ID, or correction history is returned.
- no per-row source version.
- no explicit corporate-action audit.

## License / storage / redistribution

- AKShare is an open-source wrapper; its package license does not grant rights
  to the underlying Sina data.
- The Sina endpoint has no documented storage/redistribution permission in the
  AKShare response.
- Internal research use may be possible, but repository artifact publication
  and redistribution are **not verified**.
- No approval to add AKShare to `approved_providers`.

## Contract assessment

| Requirement | AKShare |
|---|---|
| independent identifiable source | yes (Sina) |
| exact date | yes |
| valid raw OHLCV | yes for 503 |
| price-basis consistency | raw/qfq available; no `Adj_Close` field |
| provenance URL/hash | adapter can record URL + SHA-256 |
| update/revision evidence | **absent** |
| documented storage/redistribution rights | **not verified** |
| tests | fixture + coverage tests; no live CI dependency |

**Not approved.** Policy remains:

```text
blocked_no_approved_fallback
approved_providers = []
```

## Tests

- `tests/test_akshare_assessment.py`: **2 passed**
  - 503 rows, unique tickers, valid OHLCV;
  - HUBB row exact and no `Adj_Close` claim.

No canonical CSV or production path was modified.

## Next actions

1. Review Sina/AKShare data-use and storage terms.
2. Obtain provider revision/update metadata if available.
3. Decide whether a raw-only, AKShare-specific contract is acceptable.
4. Only then consider approval; do not fill HUBB manually.
