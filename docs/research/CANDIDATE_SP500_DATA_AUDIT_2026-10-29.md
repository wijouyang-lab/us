# Candidate Panel Audit: Johnbrick123/sp500-data

Date: 2026-10-29 UTC
Decision: **REJECT FOR IMPORT 鈥?no data licence; no price sample downloaded.**

## 1. Source and licence

Repository:

https://github.com/Johnbrick123/sp500-data

Checked:

- README;
- GitHub repository metadata;
- file list;
- `verify.py` / `fetch_prices.py` headers;
- release verification report;
- release `recycled_tickers.csv`;
- no `LICENSE` file found.

Result:

| Item | Finding |
|---|---|
| Code licence | **none found**; GitHub API `license = null`; no LICENSE file |
| Data licence | **none stated** |
| Redistribution terms | **not stated** |
| Upstream sources | CRSP, Tiingo, Yahoo, WIKI/Quandl, Internet Archive, Nasdaq checks |
| CRSP use | licensed/subscription data; redistribution not established |
| Tiingo use | free key but redistribution terms not established |
| Yahoo/IA/WIKI | terms not established for bulk storage/redistribution |

A public GitHub repository is not a data licence. MIT-like code, even if it
existed, would not cover CRSP/Tiingo/Yahoo-derived prices.

## 2. Upstream source roles (as claimed by the project)

| Source | Claimed role | Licence problem |
|---|---|---|
| CRSP | 1970鈥?995 prices/membership; 1996+ return checks | restricted; cannot redistribute |
| Tiingo | delisted-name recovery | free key, but bulk redistribution unclear |
| WIKI/Quandl | historical delisted names | dataset/terms unclear |
| Yahoo | current/adjusted price source | redistribution restricted |
| Internet Archive | archived recoveries | content rights unclear |
| Nasdaq | cross-check | not a redistribution licence |

No source-by-source written permission is included.

## 3. Internal consistency problems

| Metric | README | Release verification |
|---|---:|---:|
| Rows | 12,285,625 | **5,676,289** |
| Tickers | 1,895 | **916** |
| Recycled tickers | 17 | **14** in released CSV |
| File size | 235 MB | 153 MB snapshot |

The release verification also reports:

```text
1996-01-02: 216 / 492 members with prices = 43.9%
worst coverage: 43.9% - pre-2005 not survivorship-safe
```

So even the project's own self-check does not support using pre-2005 history as
a complete survivorship-free panel. Its "PASS 40 / FAIL 0 / UNVERIFIED 0"
summary is self-reported, not independent.

## 4. Small-sample attempt

Requested sample:

```text
ADCT, ALTR, BRCM, CA, TWX, ALXN, XLNX, NUAN, CTXS, TWTR,
ATVI, SIVB, FRC, PBCT, CERN, ABMD, WLTW, WCOM, LEHM, BSC
```

Result:

| Item | Value |
|---|---:|
| Price rows downloaded | **0** |
| Names identity-verified | **0** |
| Names OHLCV-verified | **0** |
| Names accepted | **0** |
| Status | blocked_no_data_license |

No `prices.parquet` was downloaded. This is deliberate: without a data licence,
downloading or copying a 153鈥?35 MB panel would already exceed the permitted
evaluation scope.

Therefore this audit cannot claim the candidate recovers any of the 202 missing
names. It also cannot claim the candidate is bad on price quality; price quality
is simply **unverified**.

## 5. Coverage impact

```text
202 missing historical names recovered: 0
new verified OHLCV rows: 0
new canonical rows: 0
2016 coverage: unchanged at 336/484
```

The existing 503-name pane remains unchanged.

## 6. Answers

1. **Acceptable source/use licence?**
   No. No code or data licence; upstream CRSP/Tiingo/Yahoo/WIKI/IA rights are
   unresolved.

2. **How many of the 202 missing names were recovered?**
   Zero imported or verified. The sample was not downloaded because the licence
   gate failed.

3. **Did the data pass independent identity/date/OHLC/action checks?**
   No independent check was possible or attempted. Candidate self-checks were
   read only; their own coverage check reports 43.9% for 1996.

4. **Can it materially improve historical universe coverage?**
   Cannot be used in this project under current terms, so no. Any claimed
   coverage remains the vendor/author's claim, not project evidence.

5. **What still blocks full PIT backtesting?**
   - no data licence/redistribution rights;
   - no verified delisted OHLC;
   - unresolved ticker reuse;
   - no independent adjusted-close/corporate-action verification;
   - membership still community-derived and not official;
   - current panel remains survivorship-biased.

## 7. Artifacts

- manifest: `docs/research/candidate_sp500_data_manifest_2026-10-29.json`
- sample status: `docs/research/candidate_panel_sample_2026-10-29.csv`
- gate: `tools/research/candidate_panel_gate.py`
- tests: `tests/test_candidate_panel_gate.py`

## 8. Stop condition

Do not import this dataset. Do not download its full Parquet panel. Do not use
its prices in the canonical panel or in public results.

Further work requires a source with explicit data rights, or a written licence
from the candidate author/upstream vendors.
