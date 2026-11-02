# Data Feasibility and Stop Condition

Date: 2026-10-30
Research only. No production changes.

## 1. SEC company facts 鈥?actual sample

Endpoint:

```text
https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json
```

HTTP 200 for 5/5 sampled issuers.

| Ticker | CIK | Assets | Revenue | Cost | Gross profit | First filed |
|---|---|---|---|---|---|---|
| AAPL | 0000320193 | yes | yes | yes | yes | 2009-07-22 |
| MSFT | 0000789019 | yes | yes | yes | yes | 2009-10-23 |
| JNJ | 0000200406 | yes | yes | yes | yes | 2009-08-04 |
| XOM | 0000034088 | yes | yes | no | no | 2009-08-05 |
| WMT | 0000104169 | yes | yes | yes | no | 2009-09-09 |

Conclusion:

- assets and revenue are broadly available;
- cost / gross-profit tags are **not uniform** (2/5 lacked gross profit);
- XBRL history starts around 2009, not a full 20-year history;
- `filed` is a **date**, not an exact acceptance/publication timestamp;
- companyfacts facts do not carry accession-level acceptance time.

Evidence:

`docs/research/sec_companyfacts_feasibility_2026-10-30.json`

## 2. SEC submissions

`https://data.sec.gov/submissions/CIK0000320193.json`

- HTTP 200;
- 1,002 recent form rows;
- `acceptanceDateTime` exists at filing level;
- this is filing metadata, not first-public-visibility proof;
- no ticker history / delisted universe.

## 3. Historical tickers, delisted securities, index constituents

| Source | Actual result |
|---|---|
| SEC `company_tickers.json` | HTTP **403** with current client |
| SEC companyfacts | current filer mapping only; no ticker history |
| Wikipedia current S&P 500 table | current 503-name table with Symbol/CIK/Date added |
| Wikipedia historical-components page | prose only; **no machine-readable table** |
| Nasdaq Trader delisted | previously blocked; not retried |
| Stooq / other free price sources | previously blocked / anti-bot; not retried |

The current S&P 500 page provides current membership, not point-in-time
membership. It cannot remove survivorship bias.

## 4. Stop condition

The minimum requirements for a credible fundamental PIT candidate are not met:

1. no point-in-time index membership;
2. no reliable historical ticker / delisted-security mapping;
3. fundamentals have date-only `filed`, not exact public availability;
4. gross-profit / cost tags are not uniform across issuers;
5. no accession-level join from companyfacts to exact acceptance timestamps.

Therefore this round **does not** build a quality/value/profitability backtest.
Doing so would either:

- use current-universe data and overstate performance; or
- treat `filed` as intraday PIT availability, which is false.

## 5. What would unlock the next round

At minimum:

- historical index membership with effective dates;
- historical ticker / CIK / delisting mapping;
- exact filing acceptance or a conservative next-session availability rule;
- a uniform fundamental schema across the universe.

Free sources tested do not provide all four.

## 6. Status of existing candidates

- Qlib-inspired composite: rejected (positive 2023-2026 excess, negative 2018-2022).
- Momentum-only: rejected (near-zero earlier-period excess).
- No new candidate admitted.
- PIT event sample: 0 admitted events.
- No production/logic changes.

## 7. Reproduce

The SEC sample can be reproduced with:

```bash
python - <<'PY'
import requests
for cik in ["0000320193","0000789019","0000200406","0000034088","0000104169"]:
    r=requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
                   headers={"User-Agent":"Mozilla/5.0"}, timeout=60)
    print(cik, r.status_code, len(r.text))
PY
```
