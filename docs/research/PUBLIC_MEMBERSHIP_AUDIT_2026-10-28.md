# Public S&P 500 Membership Dataset Audit

Date: 2026-10-28
Research only. Membership is not OHLCV.

## Sources inspected

### shardul0701/SP500-Survivorship-bias-data-2004-2026

- Source: https://github.com/shardul0701/SP500-Survivorship-bias-data-2004-2026
- License: data derived from `fja05680/sp500`, MIT license notice included in
  `licenses/fja05680_sp500_LICENSE`.
- Files: 23 annual YAML files, 2004鈥?026.
- Fields: `year`, `tickers_on_Jan_1`, dated changes.
- Actual parsed union: **972 tickers**.
- README limitations: community data, post-2019 reconciled against official
  announcements; pre-2016 reconstruction should be treated as less validated.

### coiltrade/point-in-time-sp500

- Source: https://github.com/coiltrade/point-in-time-sp500
- Code license: MIT.
- Data license: CC BY 4.0 (README).
- File: `data/membership.json`.
- Fields: `current` (503 names as of 2026-06-30) and 402 dated `changes`.
- Actual change date range: **1976-07-01 to 2026-06-30**.
- Actual parsed union: **874 tickers**.
- README limitation: no price data; delisted price coverage remains a separate
  problem.

## Coverage comparison

Current 10-year price panel: **503 tickers**.
Failed PIT tickers: **98**.

| Dataset | All membership tickers | Failed overlap | Failed missing | Membership not in price panel |
|---|---:|---:|---:|---:|
| coiltrade | 874 | **91/98** | 7 | **381** |
| shardul | 972 | **94/98** | 4 | **491** |

Missing from coiltrade: `ACS, CBS, MYL, PARA, PX, UA.C, WRK`.
Missing from shardul: `TSO, UA.C, WYN, YHOO`.

These are **membership/identity gaps only**. They do not add any OHLCV rows.

## What this changes

- The public datasets can substantially improve historical **membership**
  coverage: roughly 381鈥?91 additional historical member tickers beyond the
  current-universe price panel.
- They cannot fill the 98 price holes. The current price panel still has
  **503** tickers and the same 91.61% member-session coverage.
- They cannot be used to claim survivorship-free returns unless each historical
  member also has verified prices and corporate actions.

## Limitations

1. Membership is not price data.
2. Community/derived history must be checked against official changes for
   disputed dates.
3. Ticker changes and CIK identity still need separate mapping.
4. No membership dataset resolves delisted OHLCV.
5. Data licenses are documented; no data was copied into the production repo.

## Reproducible audit

```bash
python tools/research/audit_public_membership.py \
  --coiltrade datasets/coiltrade/data/membership.json \
  --shardul-dir datasets/shardul/src/sp500_ticker_history \
  --price-panel research_price_history_sp500_10y.csv \
  --failed-csv docs/research/missing_tickers_classification_2026-10-28.csv \
  --output docs/research/public_membership_audit_2026-10-28.json
```

Tests: `tests/test_audit_public_membership.py`.

## Decision impact

Membership coverage improves, but **price coverage does not**. The full-history
PIT strategy validation remains frozen until an independent OHLCV source and
delisted price history are verified.
