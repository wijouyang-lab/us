# AkShare 美股 28 家覆盖验证 — P5.2

## 目的

验证 AkShare 能否为 P5.1 的固定 28 家研究样本提供：

- 当前报价快照；
- 2016-01-01 至运行日的日频 OHLCV；
- 可供后续复核的基本行情质量统计。

本工具只进行只读数据请求，不写入生产行情表，不更新 Dashboard，不生成估值或策略分数，不下单。

## 重要的已有证据

仓库此前已有 \`docs/research/akshare_us_sample_2026-10-30.json\`。该文件记录：

| Symbol | Rows | First date | Last date | Missing close | Duplicates | Invalid OHLC |
|---|---:|---|---|---:|---:|---:|
| AAPL | 10,064 | 1984-09-07 | 2026-10-29 | 0 | 0 | 0 |
| MSFT | 9,682 | 1986-03-13 | 2026-10-29 | 0 | 0 | 0 |
| NVDA | 5,796 | 1999-01-22 | 2026-10-29 | 0 | 0 | 0 |
| TSLA | 3,935 | 2011-01-26 | 2026-10-29 | 0 | 0 | 0 |
| SPY | 6,494 | 2001-01-02 | 2026-10-29 | 0 | 0 | 1 |

AAPL stability check was recorded as \`same_shape=true\`, \`same_last_close=true\`.

This demonstrates that the historical endpoint previously returned long US equity series for these four stocks and one ETF. It does **not** establish coverage for the P5.1 28-company sample, independent-source accuracy, corporate-action correctness, or production eligibility.

## Current official API implementation checked

AkShare's current source code for \`stock_us_spot_em()\` identifies it as an Eastmoney US quote snapshot and explicitly labels it 15-minute delayed. The returned fields include latest price, total market capitalization, PE, and provider symbol (\`代码\`).

\`stock_us_hist()\` accepts the provider symbol returned by the spot endpoint, supports daily/weekly/monthly bars and \`qfq\`/\`hfq\`/unadjusted modes, and returns date, OHLC, volume, turnover, and related fields.

Source code:
- https://github.com/akfamily/akshare/blob/main/akshare/stock/quote/stock_hist_em.py

## How to run

The one-off GitHub Actions workflow attached to this research PR runs the audit and uploads a 30-day artifact. It does not push a commit or change the default branch.

Manual local command:

\`\`\`bash
python -m pip install pandas akshare
python tools/research/akshare_us_28_coverage.py \\
  --output artifacts/akshare-us-28-coverage.json \\
  --start-date 20160101 \\
  --adjust qfq \\
  --sleep-seconds 0.8
\`\`\`

The report records:
- spot symbol match, ambiguity, price availability, raw market-cap and PE fields;
- daily history rows and available date range;
- missing OHLC/close, duplicate dates, zero-volume rows, invalid OHLC and non-positive prices;
- quote vs latest history close difference as a diagnostic only;
- AkShare package version and execution timestamp.

## Interpretation rules

A positive quote and nonempty, internally consistent history are **data availability evidence only**. They do not make a company Value-ready or Trend-ready.

Before Value uses any quote:
1. verify quote currency and units;
2. pair with a correctly timed SEC shares-outstanding fact;
3. calculate market capitalization consistently;
4. retain source, observation time, and filing/publication availability time.

Before Trend uses adjusted prices:
1. compare raw and adjusted prices around known splits/dividends;
2. verify the adjustment basis and historical revisions;
3. retain the existing PIT membership/coverage gates;
4. do not treat the 28-company sample as a point-in-time universe.

This audit does not test forward EPS, does not replace SEC fundamentals, and does not establish historical option/borrow/financing data for Hedge.

## Scope and safety

- Research-only; no production code, trading, stop-loss, dashboard or scan changes.
- No full SEC accession scan.
- No paid data subscription or API key.
- No raw OHLCV persisted in this report.
- AkShare output is not automatically treated as authorized for redistribution; this task only evaluates private research availability and basic integrity.
