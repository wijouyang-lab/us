# P12.5.2 Equity Price Readiness

Verdict: **DATA_BLOCKED**.

| Check | Result |
|---|---|
| Snapshot rows | 1,047,578 |
| Tickers | 502 |
| Date range | 2016-12-12 .. 2026-10-13 |
| Open/High/Low/Close | only `Price` (close) |
| Adj Close | absent |
| Split adjustment | absent |
| Dividend adjustment | absent |
| PIT membership verified | NO |
| Delisted names verified | NO |
| Events 2017+ | 236 (118 CPI, 118 Employment) |
| Events with ≥20 names | 228 |
| Median names/event | 422 |
| Same-day future price coverage | not uniform after 2026-10-13 |

The panel cannot support total-return or next-open calculations. It cannot be
used to claim a tradable CPI/Employment alpha. A date-level descriptive study is
possible only with the unadjusted-close caveat; this round stops before model
estimation because the gate failed.

Required: PIT total-return panel with delisted names, OHLC, and verified
membership, or an explicit survivorship-bias sensitivity.
