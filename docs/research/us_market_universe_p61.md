# US Market Universe Registry — P6.1

Date: 2026-11-05
Branch: `research/us-market-universe-p61`
Scope: **current listed common equity + ADR only**

## 1. Sources and timestamps

| Source | Raw file | Timestamp |
|---|---|---|
| Nasdaq Trader | `nasdaqlisted.txt` | `2026-11-04T12:11` (vendor footer; timezone not specified) |
| Nasdaq Trader | `otherlisted.txt` | `2026-11-04T12:11` (vendor footer; timezone not specified) |
| SEC | `company_tickers_exchange.json` | file fetched `2026-11-04T18:08:42Z` |

Source URLs:

```text
https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt
https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt
https://www.sec.gov/files/company_tickers_exchange.json
```

SEC is used only as a cross-mapping. SEC-unmatched records are retained.

## 2. Counts

| Metric | Count |
|---|---:|
| Raw records | **13,275** |
| Raw nasdaqlisted | 5,609 |
| Raw otherlisted | 7,666 |
| Deduplicated exact records | **13,275** |
| Current records | **5,615** |
| Common | **5,187** |
| ADR | **315** |
| UNCLASSIFIED | **113** |
| Excluded | **7,660** |
| SEC matched (all raw) | 7,144 |
| SEC unmatched (all raw) | 6,131 |
| SEC ambiguous (all raw) | 0 |
| SEC matched (current) | 5,593 |
| SEC unmatched (current) | 22 |
| SEC ambiguous (current) | 0 |

No exact duplicate `(ticker, exchange, security_name)` records were removed:
the files produced the same 13,275 record keys. No ticker was deduplicated
across a different issuer or exchange.

## 3. Exclusions

| Reason | Count |
|---|---:|
| ETF / NextShares | 5,775 |
| Preferred | 445 |
| Warrant | 457 |
| Unit | 317 |
| Fund | 266 |
| Note | 149 |
| Right | 145 |
| Test issue | 37 |
| Debenture | 23 |
| Bond | 16 |
| Depositary shares (non-ADR) | 16 |
| ETN | 14 |

## 4. Classification rules

Included:

- common stock / common shares / ordinary shares;
- Class A/B/C shares;
- American Depositary Shares / ADS / ADR / New York registry shares;
- shares of beneficial interest / REIT common names;
- `ord shares` / `registered shares`;
- `when-issued` common-stock records are included with `listing_note=WHEN_ISSUED`
  (CEG, SNDK), because they are current source records and S&P constituents.

Excluded:

- ETF, ETN, mutual funds, preferred / preference shares;
- warrants, rights, units, notes, bonds, debentures;
- depositary shares that are not American Depositary Shares;
- test issues / when-issued non-common securities.

Unknown labels remain `UNCLASSIFIED` in the current file; they are not deleted.

## 5. Coverage checks

### 28-company sample

```text
sample_28_total = 28
sample_28_missing = []
```

All 28 fixed research tickers are present in the current universe.

### S&P 500

Input: `sp500_constituents.csv` (503 tickers).

```text
sp500_total = 503
sp500_matched = 502
sp500_missing = ["KVUE"]
```

KVUE is absent from the downloaded exchange directories, not classified away
or deleted by the builder. It is reported as a source gap; no record was
fabricated.

## 6. Multi-class and duplicate checks

- Current records with explicit class names: **1,089**.
- Same ticker across different records: **0 exact duplicate keys** in this
  source snapshot.
- Multi-class examples retained separately:
  - GOOG / GOOGL (Alphabet Class C / Class A)
  - FOX / FOXA (Fox Class B / Class A)
  - NWS / NWSA (News Corp Class B / Class A)
  - BRK.A / BRK.B (Berkshire classes)
- `same_ticker_distinct_names = 0` for this snapshot; no same-ticker issuer
  collision was silently merged.

## 7. Exchange scope

Mapped:

```text
NASDAQ, NYSE, NYSE American, NYSE Arca, Cboe BZX, IEX
```

Unknown exchange codes are retained as `OTHER:<code>` rather than dropped.

**Not covered / not verified:**

- OTC markets / OTC Pink;
- unlisted or non-exchange venues;
- historical delisted securities;
- historical point-in-time membership.

This registry is current listing status only. It is **not** a historical PIT
universe and must not be used as one.

## 8. Files

```text
data/universe/us_equities_current.csv
data/universe/us_equities_excluded.csv
data/universe/us_equities_universe_audit.json
data/universe/source/nasdaqlisted.txt
data/universe/source/otherlisted.txt
data/universe/source/company_tickers_exchange.json
tools/research/build_us_market_universe.py
tests/test_us_market_universe_p61.py
```

## 9. Tests

```text
tests/test_us_market_universe_p61.py  7 passed
```

Covered:

- common / ADR / preferred / warrant / unit / test / ETF classification;
- pipe parsing and vendor footer timestamp;
- actual output counts;
- excluded file contains only excluded records;
- all 28 sample tickers present;
- multi-class examples retained.

## 10. Limitations

1. `KVUE` is missing from both Nasdaq Trader source files; recorded, not filled.
2. 113 current records remain `UNCLASSIFIED` because the name does not prove
   common equity or ADR; they remain visible for later review.
3. 6,131 raw records are SEC-unmatched; most are excluded funds/ETF/test rows,
   but the registry does not delete them from raw accounting.
4. Vendor footer timestamps do not specify a timezone.
5. No OTC, historical delisted, or PIT membership coverage is claimed.
6. No production scan, scoring, trading, Dashboard, or PR #497 changes.
