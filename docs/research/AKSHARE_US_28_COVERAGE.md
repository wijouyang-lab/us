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

## 实测结果（2026-11-04, AkShare 1.20.27）

Run: https://github.com/wijouyang-lab/us/actions/runs/41869374916

Artifact: `akshare-us-28-coverage` (ID 13344441792)

| 指标 | 结果 |
|---|---|
| 28 家当前报价成功 | **28/28** |
| 28 家历史行情成功 | **28/28** |
| 28 家历史行情质量通过 | **23/28** |
| Value 输入就绪 | **23/28** |
| GARP 前瞻 EPS 就绪 | **0/28** |
| Trend 历史质量通过 | **23/28** |
| 原始/前复权对照尝试 | **5/28**（全部通过） |
| SCORE_READY | **0/28** |
| BACKTEST_READY | **0/28** |

### 逐股结果

| Ticker | Vendor symbol | Spot | Quote | Market cap raw | Rows | First | Last | QFQ quality | Value | Cap ratio |
|---|---|---|---:|---:|---:|---|---|---|---:|---:|
| AAPL | `105.AAPL` | QUOTE_PRICE_OK | 352.93 | 5128842993260.0 | 2726 | 2016-01-04 | 2026-11-04 | DATA_QUALITY_PASS | VALUE_INPUT_READY | 1.0 |
| MSFT | `105.MSFT` | QUOTE_PRICE_OK | 556.2 | 4130449409822.0 | 2726 | 2016-01-04 | 2026-11-04 | DATA_QUALITY_PASS | VALUE_INPUT_READY | 0.9999999999999031 |
| GOOGL | `105.GOOGL` | QUOTE_PRICE_OK | 290.64 | 3573128160000.0 | 2726 | 2016-01-04 | 2026-11-04 | DATA_QUALITY_PASS | VALUE_INPUT_READY | 1.0 |
| NVDA | `105.NVDA` | QUOTE_PRICE_OK | 202.405 | 4877960500000.0 | 2726 | 2016-01-04 | 2026-11-04 | DATA_QUALITY_FAIL | VALUE_INPUT_READY | 1.0 |
| CRM | `106.CRM` | QUOTE_PRICE_OK | 227.37 | 187125510000.0 | 2726 | 2016-01-04 | 2026-11-04 | DATA_QUALITY_PASS | VALUE_INPUT_READY | 1.0 |
| ADBE | `105.ADBE` | QUOTE_PRICE_OK | 251.975 | 98068670000.0 | 2726 | 2016-01-04 | 2026-11-04 | DATA_QUALITY_PASS | VALUE_INPUT_READY | 1.0 |
| AMZN | `105.AMZN` | QUOTE_PRICE_OK | 267.396 | 2891386686530.0 | 2726 | 2016-01-04 | 2026-11-04 | DATA_QUALITY_PASS | VALUE_INPUT_READY | 0.9999988780685918 |
| HD | `106.HD` | QUOTE_PRICE_OK | 352.44 | 351625731787.0 | 2726 | 2016-01-04 | 2026-11-04 | DATA_QUALITY_FAIL | VALUE_INPUT_READY | 0.9999999999987487 |
| MCD | `106.MCD` | QUOTE_PRICE_OK | 277.21 | 196165308809.0 | 2726 | 2016-01-04 | 2026-11-04 | DATA_QUALITY_PASS | VALUE_INPUT_READY | 1.000000000002498 |
| NKE | `106.NKE` | QUOTE_PRICE_OK | 40.925 | 60786263827.0 | 2726 | 2016-01-04 | 2026-11-04 | DATA_QUALITY_PASS | MARKET_CAP_UNIT_OR_VALUE_MISMATCH | None |
| CAT | `106.CAT` | QUOTE_PRICE_OK | 586.27 | 269493597174.0 | 2726 | 2016-01-04 | 2026-11-04 | DATA_QUALITY_PASS | VALUE_INPUT_READY | 0.9999453752446135 |
| HON | `105.HON` | QUOTE_PRICE_OK | 230.56 | 73170179910.0 | 2726 | 2016-01-04 | 2026-11-04 | DATA_QUALITY_FAIL | VALUE_INPUT_READY | 0.9998693068672118 |
| UNP | `106.UNP` | QUOTE_PRICE_OK | 305.91 | 181787144759.0 | 2726 | 2016-01-04 | 2026-11-04 | DATA_QUALITY_PASS | VALUE_INPUT_READY | 1.0000000000024203 |
| XOM | `106.XOM` | QUOTE_PRICE_OK | 169.83 | 692774755587.0 | 2726 | 2016-01-04 | 2026-11-04 | DATA_QUALITY_PASS | VALUE_INPUT_READY | 1.0000551228109698 |
| CVX | `106.CVX` | QUOTE_PRICE_OK | 216.41 | 425245650000.0 | 2726 | 2016-01-04 | 2026-11-04 | DATA_QUALITY_PASS | VALUE_INPUT_READY | 0.9945483193617887 |
| NEE | `106.NEE` | QUOTE_PRICE_OK | 88.18 | 184940447401.0 | 2726 | 2016-01-04 | 2026-11-04 | DATA_QUALITY_FAIL | SHARES_NOT_CURRENT | 1.0059021817755593 |
| DUK | `106.DUK` | QUOTE_PRICE_OK | 129.45 | 100932448884.0 | 2726 | 2016-01-04 | 2026-11-04 | DATA_QUALITY_PASS | SHARES_NOT_CURRENT | 1.0001359370387488 |
| JNJ | `106.JNJ` | QUOTE_PRICE_OK | 272.335 | 655594841291.0 | 2726 | 2016-01-04 | 2026-11-04 | DATA_QUALITY_PASS | VALUE_INPUT_READY | 0.9999999999998322 |
| PFE | `106.PFE` | QUOTE_PRICE_OK | 30.56 | 174187530080.0 | 2726 | 2016-01-04 | 2026-11-04 | DATA_QUALITY_PASS | VALUE_INPUT_READY | 0.9999999999972444 |
| UNH | `106.UNH` | QUOTE_PRICE_OK | 405.465 | 363305807969.0 | 2726 | 2016-01-04 | 2026-11-04 | DATA_QUALITY_PASS | VALUE_INPUT_READY | 0.9982483901221821 |
| MRNA | `105.MRNA` | QUOTE_PRICE_OK | 248.26 | 99114301803.0 | 1988 | 2018-12-07 | 2026-11-04 | DATA_QUALITY_PASS | VALUE_INPUT_READY | 0.9999999999985875 |
| JPM | `106.JPM` | QUOTE_PRICE_OK | 350.34 | 930366235383.0 | 2726 | 2016-01-04 | 2026-11-04 | DATA_QUALITY_FAIL | VALUE_INPUT_READY | 0.9990306600775304 |
| BAC | `106.BAC` | QUOTE_PRICE_OK | 51.225 | 353463206332.0 | 2726 | 2016-01-04 | 2026-11-04 | DATA_QUALITY_PASS | VALUE_INPUT_READY | 0.9999999999990097 |
| BRK.B | `106.BRK_B` | QUOTE_PRICE_OK | 573.74 | 1228211047772.0 | 2726 | 2016-01-04 | 2026-11-04 | DATA_QUALITY_PASS | MARKET_CAP_UNIT_OR_VALUE_MISMATCH | None |
| MET | `106.MET` | QUOTE_PRICE_OK | 101.32 | 64386522244.0 | 2726 | 2016-01-04 | 2026-11-04 | DATA_QUALITY_PASS | VALUE_INPUT_READY | 1.0000000000055913 |
| PLD | `106.PLD` | QUOTE_PRICE_OK | 128.38 | 122026858940.0 | 2726 | 2016-01-04 | 2026-11-04 | DATA_QUALITY_PASS | SHARES_NOT_CURRENT | 1.0194940032477493 |
| O | `106.O` | QUOTE_PRICE_OK | 59.055 | 56161130670.0 | 2726 | 2016-01-04 | 2026-11-04 | DATA_QUALITY_PASS | VALUE_INPUT_READY | 1.0000000000064102 |
| RIVN | `105.RIVN` | QUOTE_PRICE_OK | 13.955 | 20368838543.0 | 1251 | 2021-11-10 | 2026-11-04 | DATA_QUALITY_PASS | VALUE_INPUT_READY | 0.9997319438213829 |

### 行情质量异常

- NVDA：`nonpositive_ohlc=20`，历史 OHLC 存在非正价格行，质量门禁失败。
- HD、HON、NEE、JPM：各 `invalid_ohlc=1`，存在 high/low/open/close 逻辑异常行，质量门禁失败。
- 以上 5 家不能被标记为 DATA_QUALITY_PASS；其余 23 家通过基础 OHLCV 检查。
- 这不是复权正确性的证明，也没有通过 PIT 成员覆盖门禁。

### Value 输入失败原因

- NKE：SEC 最新股数为 2015-07-17 的旧披露，且市值比例不匹配。
- BRK.B：SEC 取到的 941,481 股不是 BRK-B 当前股本（份额类别不匹配），市值比例异常。
- NEE、DUK、PLD：SEC 股数披露超过 183 天，按当前股本门禁标记 `SHARES_NOT_CURRENT`。
- 其余 23 家：股价 × 股数与 AkShare 总市值在 10% 内匹配，标记 `VALUE_INPUT_READY`；这不等于 Value 评分完成。

### 原始/前复权对照

为避免再次触发东方财富限流，首轮全量 raw 获取失败后，最终只对前 5 家（AAPL、MSFT、GOOGL、NVDA、CRM）做 raw 对照；5/5 通过基础 OHLCV 检查。其余 23 家标记 `RAW_COMPARISON_NOT_ATTEMPTED`，不能声称已完成全量复权验证。

### 限流记录

- 第一次增强运行 `41865189581`：`Push2RateLimitError`，spot 请求被限流，未取得数据。
- 冷却后第二次运行 `41869374916` 成功，使用 `--raw-limit 5` 控制请求量。
- 不通过重复请求绕过限流。

### 结论边界

```text
DATA_AVAILABLE:     28/28 spot + history nonempty
DATA_QUALITY_PASS:  23/28 qfq basic OHLCV
INPUT_READY:        23/28 Value market-cap inputs
SCORE_READY:         0/28
BACKTEST_READY:      0/28
GARP forward EPS:    0/28
```

AkShare 能补齐当前报价、历史 OHLCV 和大部分 Value 市值输入，但不能单凭这些数据解除 Value 的整体 DATA_BLOCKED：仍缺可审计的 PIT 股价、股本时效、公司行动口径和跨源验证。GARP 的前瞻 EPS 仍然缺失；Trend 的 PIT 95%/98% 门禁未通过。
