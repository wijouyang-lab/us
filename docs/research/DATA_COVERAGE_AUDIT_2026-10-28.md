# Missing Ticker and Free Data Source Audit

Date: 2026-10-28
Research only. No production changes.

## 1. Failure set

Source audit run: `40333146481`
`download_failure_count = 98`
Member-session coverage: **91.61%** (1,171,451 / 1,278,758)
Ticker coverage at 90% threshold: **84.23%** (593 / 704)

The full per-ticker classification is in:

`docs/research/missing_tickers_classification_2026-10-28.csv`

Summary:

| Category | Count | Basis |
|---|---:|---|
| Active listing but price source failed | 1 (`PARA`) | Ticker exists in current SEC company ticker map |
| Not in current SEC map after alias check; delisted/acquired/renamed or unresolved | 97 | SEC current map absence plus audit fallback 404/delisted errors |

Absence from the SEC current-ticker file is **not proof of delisting**. It
means the exact ticker is not currently registered in that file; the audit
evidence is consistent with delisting/merger/name change, but each company
still needs filing/announcement verification.

Examples with strong delisting/merger context include ABMD, AET, AGN, ALXN,
ATVI, CELG, CERN, DISCA/DISCK, DWDP, ESRX, MON, MYL, NBL, PXD, RTN, SIVB,
TWTR, XLNX, YHOO. These are contextual examples, not a substitute for a
filing-by-filing verification.

## 2. Actual free-source tests

### SEC EDGAR company ticker map

- URL: `https://www.sec.gov/files/company_tickers.json`
- Downloaded successfully: **10,429 current ticker records**
- Free: yes
- API key: no
- Independent of Yahoo: **yes** for identity/filings
- OHLCV: **no**
- Delisted historical prices: **no**
- Coverage for the 98: 1 current ticker match (`PARA`); 97 not in the current map

SEC can verify issuer identity/CIK and filings. It cannot replace an OHLCV
history source.

### Stooq free historical endpoint

Tested:

```text
https://stooq.com/q/d/l/?s=avb.us&i=d
```

Actual result: HTTP response was an HTML JavaScript browser challenge
(796 bytes), not a CSV. **No rows were retrieved.** The endpoint is not
script-accessible in this environment without solving the JS challenge, and
its delisted-history coverage cannot be verified.

### Internet Archive

Already attempted by the PIT refresh audit:

```text
attempted_ticker_count = 98
recovered_ticker_count = 0
```

No archived legacy Yahoo CSV was usable for these names. It is not a reliable
free replacement in this environment.

### Yahoo Finance

This is the existing source. Re-reading it is **not** an independent
multi-source check. It failed for these 98 names.

### OpenBB

- `openbb` is not installed.
- The PyPI `openbb==5.0.0` wheel is a small meta-package requiring a large
  provider stack (`openbb-core`, yfinance, FMP, Polygon, Tiingo, SEC, etc.).
- No provider API keys are available.
- No OpenBB request was made.
- Free yfinance would still be the same Yahoo source; independent verification
  is blocked.

## 3. Survivorship / PIT assessment

- 10-year price panel: 1,233,984 rows, 503 current-universe tickers.
- It does not contain the 98 failed membership tickers.
- Therefore the 10-year panel cannot represent the historical S&P 500
  investable universe without survivorship bias.
- The 2-year PIT snapshot has 502 tickers, 462 sessions, but is still a
  short-window panel.
- Missing records remain missing. No interpolation, no other-ticker price
  substitution, no deletion to improve coverage.

## 4. Quantitative acceptance standard

A data source must meet all of the following before model research can resume:

| Criterion | Threshold | Current |
|---|---|---:|
| Member-session bar coverage | >= 95% | 91.61% |
| Ticker coverage at 90% per ticker | >= 98% | 84.23% |
| Delisted/acquired membership coverage | >= 98% of membership tickers | 0/98 fully recovered |
| Unverifiable missing records | <= 2% | 8.39% member bars missing |
| Cross-source Close difference | <= 0.5% on matched dates | not measurable (no independent source) |
| Corporate-action consistency | no unexplained split/rename breaks | unverified |
| PIT availability time | labels/features use only data available at T | partially verified for snapshot; 10Y PIT blocked |

These thresholds are deliberately not lowered to make the current data pass.

## 5. Decision

**Free data available in this environment does not support a deployable
low-frequency strategy.**

Reasons:

1. 8.39% of expected member-session bars are missing.
2. 98 of 704 membership tickers are not fully recovered.
3. 97/98 are absent from the current SEC ticker map; 1 is current but failed
   at the price provider.
4. Stooq is JS-challenged, Internet Archive recovered 0, and OpenBB has no
   independent free provider credentials.
5. The 10-year panel is current-universe and cannot be used as a
   survivorship-free PIT history.

Model research stays paused. No factor/model result from the biased panel is
treated as deployable.

## 6. Next unblock options

- Obtain a lawful delisted-history source or institutional data access.
- Verify each of the 97 non-current tickers against SEC filings/merger records
  before deciding whether identity-only recovery is enough.
- If only current-universe research is desired, explicitly relabel it as
  exploratory and exclude it from production decisions.
- Do not fill missing prices, delete hard tickers, or lower the coverage
  denominator.
