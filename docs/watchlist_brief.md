# Watchlist Brief — 24 只

> 生成：`scripts/ticker_brief.py --watchlist ... --md`　仓库：us　日期：latest

- 共 **24** 只票（AMT, AVGO, CDNS, NXPI, DVN, FAST, NDAQ, ADI, CSX, TXN, COP, AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA, TSM, BRK-B, JPM, V, UNH, XOM）：**5** 只有 AI 快照记录，**9** 只有交易记录

## 宏观环境（结论化，仅打印一次）

- 恐惧贪婪指数：**29.80（恐惧）**　时间戳：2026-10-27T12:44:37+00:00
- FedWatch（会议 2026-10-28，目标区间 3.75%-4.00%）：维持不变 **88.9%** / 加息 25bp **11.1%**
- 宏观指标：
  - 10Y国债：**4.99%**（前值 4.99%，2026-10-27，N/A）
  - 5Y国债：**4.83%**（前值 4.82%，2026-10-27，N/A）
  - 13周国债：**4.04%**（前值 4.03%，2026-10-27，N/A）
  - CPI：**3.74%**（前值 N/A，2026-09-01，N/A）
  - 核心CPI：**2.57%**（前值 N/A，2026-09-01，N/A）
  - 失业率：**4.20%**（前值 4.10%，2026-09-01，N/A）
- 美联储讲话：最近一次 **Trump**（10-25 04:26，Yahoo Finance）：President Donald Trump Just Proclaimed, "Tariffs Don't Cause Inflation, They Cause Wealth," but Data From Federal Reserve Economists Show Otherwise - Yahoo Finance　立场：**N/A**

---

## 1. `AMT`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：1

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-26 | Core_Dragon | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-27（该日共 292 只；全表 15 个日期 / 4237 行）
- Sector：N/A　Price：N/A
- 提示：该 ticker 在 2026-10-27 无因子快照

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 样本数：1（按日期倒序展示最近 1 笔）

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-26 18:27:07 | AMT | 买入 | 188.28 | 53 | 9978.84 | 0.00 |

---

## 2. `AVGO`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-27（该日共 292 只；全表 15 个日期 / 4237 行）
- Sector：Technology　Price：329.17

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -1.6199 | 24 |
| Momentum_20D_Pct | -5.8357 | 21 |
| Momentum_60D_Pct | -15.4413 | 14 |
| Realized_Volatility_20D_Pct | 39.5293 | 75 |
| Volume_Ratio_20D | 0.8559 | 36 |
| ZScore_20D | -1.2634 | 18 |
| Beta_60D_SPY | 2.1264 | 86 |
| Stock_RS_20D_vs_SPY | -5.8044 | 21 |
| Quant_Score | 82.0000 | 99 |
| MA20 | 347.6900 | 90 |
| MA50 | 355.4800 | 90 |
| ATR_Pct | 3.4000 | 66 |
| KDJ_J | 15.0100 | 18 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 3. `CDNS`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-27（该日共 292 只；全表 15 个日期 / 4237 行）
- Sector：Other　Price：322.17

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -1.1324 | 26 |
| Momentum_20D_Pct | -1.3866 | 33 |
| Momentum_60D_Pct | -5.2497 | 39 |
| Realized_Volatility_20D_Pct | 40.2058 | 77 |
| Volume_Ratio_20D | 2.0493 | 98 |
| ZScore_20D | -0.8534 | 26 |
| Beta_60D_SPY | 1.5443 | 77 |
| Stock_RS_20D_vs_SPY | -1.3552 | 33 |
| Quant_Score | 82.0000 | 99 |
| MA20 | 335.1700 | 88 |
| MA50 | 318.7800 | 87 |
| ATR_Pct | 3.7500 | 75 |
| KDJ_J | 44.8300 | 36 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：10（按日期倒序展示最近 10 笔）
- **历史同类交易汇总**：共 5 笔，胜率 60.0%，平均盈利 +$248.47，平均亏损 -$310.52，盈亏比 0.80

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-22 11:30:00 | APA | 卖出 | 48.14 | 200 | 9628.00 | -324.00 |
| 2026-10-19 18:26:47 | APA | 买入 | 49.76 | 200 | 9952.00 | 0.00 |
| 2026-10-16 18:26:27 | ADSK | 卖出 | 237.81 | 43 | 10225.83 | 274.77 |
| 2026-10-14 18:27:00 | ISRG | 卖出 | 414.81 | 24 | 9955.44 | 233.76 |
| 2026-10-13 18:26:54 | ANET | 卖出 | 204.98 | 47 | 9634.06 | -297.04 |
| 2026-10-13 18:26:54 | KR | 卖出 | 60.68 | 168 | 10194.24 | 236.88 |
| 2026-10-07 21:44:58 | ADSK | 买入 | 231.42 | 43 | 9951.06 | 0.00 |
| 2026-10-07 21:44:58 | ANET | 买入 | 211.30 | 47 | 9931.10 | 0.00 |
| 2026-10-07 21:44:58 | ISRG | 买入 | 405.07 | 24 | 9721.68 | 0.00 |
| 2026-10-07 21:44:58 | KR | 买入 | 59.27 | 168 | 9957.36 | 0.00 |

---

## 4. `NXPI`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：2

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-23 | Core_Dragon | scan | N/A | N/A |
| 2026-10-20 | Core_Dragon | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-27（该日共 292 只；全表 15 个日期 / 4237 行）
- Sector：Other　Price：245.83

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 6.7944 | 90 |
| Momentum_20D_Pct | 4.0242 | 53 |
| Momentum_60D_Pct | 7.2744 | 74 |
| Realized_Volatility_20D_Pct | 35.4267 | 67 |
| Volume_Ratio_20D | 1.3358 | 87 |
| ZScore_20D | 1.7367 | 78 |
| Beta_60D_SPY | 1.8638 | 82 |
| Stock_RS_20D_vs_SPY | 4.0555 | 53 |
| Quant_Score | 82.0000 | 99 |
| MA20 | 234.9200 | 80 |
| MA50 | 230.5600 | 78 |
| ATR_Pct | 3.4900 | 68 |
| KDJ_J | 95.1300 | 86 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：10（按日期倒序展示最近 10 笔）
- **历史同类交易汇总**：共 5 笔，胜率 60.0%，平均盈利 +$248.47，平均亏损 -$310.52，盈亏比 0.80

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-22 11:30:00 | APA | 卖出 | 48.14 | 200 | 9628.00 | -324.00 |
| 2026-10-19 18:26:47 | APA | 买入 | 49.76 | 200 | 9952.00 | 0.00 |
| 2026-10-16 18:26:27 | ADSK | 卖出 | 237.81 | 43 | 10225.83 | 274.77 |
| 2026-10-14 18:27:00 | ISRG | 卖出 | 414.81 | 24 | 9955.44 | 233.76 |
| 2026-10-13 18:26:54 | ANET | 卖出 | 204.98 | 47 | 9634.06 | -297.04 |
| 2026-10-13 18:26:54 | KR | 卖出 | 60.68 | 168 | 10194.24 | 236.88 |
| 2026-10-07 21:44:58 | ADSK | 买入 | 231.42 | 43 | 9951.06 | 0.00 |
| 2026-10-07 21:44:58 | ANET | 买入 | 211.30 | 47 | 9931.10 | 0.00 |
| 2026-10-07 21:44:58 | ISRG | 买入 | 405.07 | 24 | 9721.68 | 0.00 |
| 2026-10-07 21:44:58 | KR | 买入 | 59.27 | 168 | 9957.36 | 0.00 |

---

## 5. `DVN`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：1

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-26 | Core_Dragon | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-27（该日共 292 只；全表 15 个日期 / 4237 行）
- Sector：Other　Price：51.64

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 1.4140 | 48 |
| Momentum_20D_Pct | 10.5072 | 84 |
| Momentum_60D_Pct | 14.4250 | 87 |
| Realized_Volatility_20D_Pct | 26.9938 | 41 |
| Volume_Ratio_20D | 0.9530 | 54 |
| ZScore_20D | 1.8367 | 82 |
| Beta_60D_SPY | -0.8817 | 2 |
| Stock_RS_20D_vs_SPY | 10.5385 | 84 |
| Quant_Score | 80.0000 | 98 |
| MA20 | 49.0500 | 21 |
| MA50 | 48.6500 | 20 |
| ATR_Pct | 2.8500 | 49 |
| KDJ_J | 82.8700 | 68 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：10（按日期倒序展示最近 10 笔）
- **历史同类交易汇总**：共 5 笔，胜率 60.0%，平均盈利 +$248.47，平均亏损 -$310.52，盈亏比 0.80

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-22 11:30:00 | APA | 卖出 | 48.14 | 200 | 9628.00 | -324.00 |
| 2026-10-19 18:26:47 | APA | 买入 | 49.76 | 200 | 9952.00 | 0.00 |
| 2026-10-16 18:26:27 | ADSK | 卖出 | 237.81 | 43 | 10225.83 | 274.77 |
| 2026-10-14 18:27:00 | ISRG | 卖出 | 414.81 | 24 | 9955.44 | 233.76 |
| 2026-10-13 18:26:54 | ANET | 卖出 | 204.98 | 47 | 9634.06 | -297.04 |
| 2026-10-13 18:26:54 | KR | 卖出 | 60.68 | 168 | 10194.24 | 236.88 |
| 2026-10-07 21:44:58 | ADSK | 买入 | 231.42 | 43 | 9951.06 | 0.00 |
| 2026-10-07 21:44:58 | ANET | 买入 | 211.30 | 47 | 9931.10 | 0.00 |
| 2026-10-07 21:44:58 | ISRG | 买入 | 405.07 | 24 | 9721.68 | 0.00 |
| 2026-10-07 21:44:58 | KR | 买入 | 59.27 | 168 | 9957.36 | 0.00 |

---

## 6. `FAST`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-27（该日共 292 只；全表 15 个日期 / 4237 行）
- Sector：Other　Price：52.47

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 2.8420 | 59 |
| Momentum_20D_Pct | 3.9216 | 51 |
| Momentum_60D_Pct | 9.9769 | 80 |
| Realized_Volatility_20D_Pct | 20.7822 | 19 |
| Volume_Ratio_20D | 0.5889 | 7 |
| ZScore_20D | 1.7177 | 77 |
| Beta_60D_SPY | 0.5234 | 51 |
| Stock_RS_20D_vs_SPY | 3.9529 | 51 |
| Quant_Score | 80.0000 | 98 |
| MA20 | 51.0800 | 22 |
| MA50 | 50.4200 | 22 |
| ATR_Pct | 2.4600 | 34 |
| KDJ_J | 96.2800 | 88 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：10（按日期倒序展示最近 10 笔）
- **历史同类交易汇总**：共 5 笔，胜率 60.0%，平均盈利 +$248.47，平均亏损 -$310.52，盈亏比 0.80

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-22 11:30:00 | APA | 卖出 | 48.14 | 200 | 9628.00 | -324.00 |
| 2026-10-19 18:26:47 | APA | 买入 | 49.76 | 200 | 9952.00 | 0.00 |
| 2026-10-16 18:26:27 | ADSK | 卖出 | 237.81 | 43 | 10225.83 | 274.77 |
| 2026-10-14 18:27:00 | ISRG | 卖出 | 414.81 | 24 | 9955.44 | 233.76 |
| 2026-10-13 18:26:54 | ANET | 卖出 | 204.98 | 47 | 9634.06 | -297.04 |
| 2026-10-13 18:26:54 | KR | 卖出 | 60.68 | 168 | 10194.24 | 236.88 |
| 2026-10-07 21:44:58 | ADSK | 买入 | 231.42 | 43 | 9951.06 | 0.00 |
| 2026-10-07 21:44:58 | ANET | 买入 | 211.30 | 47 | 9931.10 | 0.00 |
| 2026-10-07 21:44:58 | ISRG | 买入 | 405.07 | 24 | 9721.68 | 0.00 |
| 2026-10-07 21:44:58 | KR | 买入 | 59.27 | 168 | 9957.36 | 0.00 |

---

## 7. `NDAQ`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-27（该日共 292 只；全表 15 个日期 / 4237 行）
- Sector：Other　Price：104.72

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 12.3605 | 97 |
| Momentum_20D_Pct | 13.0641 | 91 |
| Momentum_60D_Pct | 11.1795 | 82 |
| Realized_Volatility_20D_Pct | 31.4765 | 58 |
| Volume_Ratio_20D | 0.9399 | 52 |
| ZScore_20D | 3.2318 | 99 |
| Beta_60D_SPY | 0.3284 | 42 |
| Stock_RS_20D_vs_SPY | 13.0955 | 91 |
| Quant_Score | 79.0000 | 98 |
| MA20 | 94.5100 | 49 |
| MA50 | 95.0200 | 49 |
| ATR_Pct | 2.2600 | 27 |
| KDJ_J | 104.1100 | 97 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：10（按日期倒序展示最近 10 笔）
- **历史同类交易汇总**：共 5 笔，胜率 60.0%，平均盈利 +$248.47，平均亏损 -$310.52，盈亏比 0.80

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-22 11:30:00 | APA | 卖出 | 48.14 | 200 | 9628.00 | -324.00 |
| 2026-10-19 18:26:47 | APA | 买入 | 49.76 | 200 | 9952.00 | 0.00 |
| 2026-10-16 18:26:27 | ADSK | 卖出 | 237.81 | 43 | 10225.83 | 274.77 |
| 2026-10-14 18:27:00 | ISRG | 卖出 | 414.81 | 24 | 9955.44 | 233.76 |
| 2026-10-13 18:26:54 | ANET | 卖出 | 204.98 | 47 | 9634.06 | -297.04 |
| 2026-10-13 18:26:54 | KR | 卖出 | 60.68 | 168 | 10194.24 | 236.88 |
| 2026-10-07 21:44:58 | ADSK | 买入 | 231.42 | 43 | 9951.06 | 0.00 |
| 2026-10-07 21:44:58 | ANET | 买入 | 211.30 | 47 | 9931.10 | 0.00 |
| 2026-10-07 21:44:58 | ISRG | 买入 | 405.07 | 24 | 9721.68 | 0.00 |
| 2026-10-07 21:44:58 | KR | 买入 | 59.27 | 168 | 9957.36 | 0.00 |

---

## 8. `ADI`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-27（该日共 292 只；全表 15 个日期 / 4237 行）
- Sector：Other　Price：407.93

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 3.4436 | 67 |
| Momentum_20D_Pct | 3.1611 | 47 |
| Momentum_60D_Pct | 11.0285 | 82 |
| Realized_Volatility_20D_Pct | 34.1537 | 63 |
| Volume_Ratio_20D | 1.1877 | 80 |
| ZScore_20D | 0.4553 | 40 |
| Beta_60D_SPY | 1.7750 | 81 |
| Stock_RS_20D_vs_SPY | 3.1925 | 47 |
| Quant_Score | 78.0000 | 97 |
| MA20 | 404.2300 | 92 |
| MA50 | 384.6700 | 92 |
| ATR_Pct | 3.3000 | 65 |
| KDJ_J | 71.0000 | 52 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：10（按日期倒序展示最近 10 笔）
- **历史同类交易汇总**：共 5 笔，胜率 60.0%，平均盈利 +$248.47，平均亏损 -$310.52，盈亏比 0.80

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-22 11:30:00 | APA | 卖出 | 48.14 | 200 | 9628.00 | -324.00 |
| 2026-10-19 18:26:47 | APA | 买入 | 49.76 | 200 | 9952.00 | 0.00 |
| 2026-10-16 18:26:27 | ADSK | 卖出 | 237.81 | 43 | 10225.83 | 274.77 |
| 2026-10-14 18:27:00 | ISRG | 卖出 | 414.81 | 24 | 9955.44 | 233.76 |
| 2026-10-13 18:26:54 | ANET | 卖出 | 204.98 | 47 | 9634.06 | -297.04 |
| 2026-10-13 18:26:54 | KR | 卖出 | 60.68 | 168 | 10194.24 | 236.88 |
| 2026-10-07 21:44:58 | ADSK | 买入 | 231.42 | 43 | 9951.06 | 0.00 |
| 2026-10-07 21:44:58 | ANET | 买入 | 211.30 | 47 | 9931.10 | 0.00 |
| 2026-10-07 21:44:58 | ISRG | 买入 | 405.07 | 24 | 9721.68 | 0.00 |
| 2026-10-07 21:44:58 | KR | 买入 | 59.27 | 168 | 9957.36 | 0.00 |

---

## 9. `CSX`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：2

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-09-28 | Observation | scan | N/A | N/A |
| N/A | N/A | legacy | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-27（该日共 292 只；全表 15 个日期 / 4237 行）
- Sector：Other　Price：51.31

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 7.1637 | 92 |
| Momentum_20D_Pct | 9.7305 | 80 |
| Momentum_60D_Pct | 1.8056 | 61 |
| Realized_Volatility_20D_Pct | 28.0514 | 45 |
| Volume_Ratio_20D | 0.8737 | 40 |
| ZScore_20D | 2.5771 | 97 |
| Beta_60D_SPY | -0.1634 | 15 |
| Stock_RS_20D_vs_SPY | 9.7619 | 80 |
| Quant_Score | 78.0000 | 97 |
| MA20 | 48.1500 | 21 |
| MA50 | 48.7400 | 20 |
| ATR_Pct | 1.9700 | 15 |
| KDJ_J | 82.8000 | 67 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：10（按日期倒序展示最近 10 笔）
- **历史同类交易汇总**：共 5 笔，胜率 60.0%，平均盈利 +$248.47，平均亏损 -$310.52，盈亏比 0.80

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-22 11:30:00 | APA | 卖出 | 48.14 | 200 | 9628.00 | -324.00 |
| 2026-10-19 18:26:47 | APA | 买入 | 49.76 | 200 | 9952.00 | 0.00 |
| 2026-10-16 18:26:27 | ADSK | 卖出 | 237.81 | 43 | 10225.83 | 274.77 |
| 2026-10-14 18:27:00 | ISRG | 卖出 | 414.81 | 24 | 9955.44 | 233.76 |
| 2026-10-13 18:26:54 | ANET | 卖出 | 204.98 | 47 | 9634.06 | -297.04 |
| 2026-10-13 18:26:54 | KR | 卖出 | 60.68 | 168 | 10194.24 | 236.88 |
| 2026-10-07 21:44:58 | ADSK | 买入 | 231.42 | 43 | 9951.06 | 0.00 |
| 2026-10-07 21:44:58 | ANET | 买入 | 211.30 | 47 | 9931.10 | 0.00 |
| 2026-10-07 21:44:58 | ISRG | 买入 | 405.07 | 24 | 9721.68 | 0.00 |
| 2026-10-07 21:44:58 | KR | 买入 | 59.27 | 168 | 9957.36 | 0.00 |

---

## 10. `TXN`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-27（该日共 292 只；全表 15 个日期 / 4237 行）
- Sector：Technology　Price：298.12

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 7.9558 | 94 |
| Momentum_20D_Pct | 7.1180 | 65 |
| Momentum_60D_Pct | 8.1163 | 76 |
| Realized_Volatility_20D_Pct | 32.1834 | 60 |
| Volume_Ratio_20D | 1.2195 | 82 |
| ZScore_20D | 2.3111 | 93 |
| Beta_60D_SPY | 1.3066 | 71 |
| Stock_RS_20D_vs_SPY | 7.1493 | 65 |
| Quant_Score | 78.0000 | 97 |
| MA20 | 284.8300 | 86 |
| MA50 | 272.7800 | 84 |
| ATR_Pct | 3.2100 | 63 |
| KDJ_J | 100.5300 | 93 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 11. `COP`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-27（该日共 292 只；全表 15 个日期 / 4237 行）
- Sector：Energy　Price：151.37

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 4.2206 | 75 |
| Momentum_20D_Pct | 20.0968 | 96 |
| Momentum_60D_Pct | 25.6391 | 95 |
| Realized_Volatility_20D_Pct | 22.4336 | 27 |
| Volume_Ratio_20D | 0.8852 | 43 |
| ZScore_20D | 1.7179 | 77 |
| Beta_60D_SPY | -1.0715 | 0 |
| Stock_RS_20D_vs_SPY | 20.1281 | 96 |
| Quant_Score | 77.0000 | 95 |
| MA20 | 137.7000 | 62 |
| MA50 | 134.5600 | 62 |
| ATR_Pct | 2.3500 | 30 |
| KDJ_J | 86.1100 | 71 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Energy）
- N/A（无成交记录）

---

## 12. `AAPL`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-27（该日共 292 只；全表 15 个日期 / 4237 行）
- Sector：Technology　Price：343.91

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 0.2828 | 37 |
| Momentum_20D_Pct | 1.6283 | 41 |
| Momentum_60D_Pct | 11.3302 | 83 |
| Realized_Volatility_20D_Pct | 16.6600 | 4 |
| Volume_Ratio_20D | 1.1079 | 73 |
| ZScore_20D | 0.9166 | 50 |
| Beta_60D_SPY | 0.1478 | 34 |
| Stock_RS_20D_vs_SPY | 1.6596 | 41 |
| Quant_Score | 27.0000 | 14 |
| MA20 | 339.1800 | 89 |
| MA50 | 330.2300 | 88 |
| ATR_Pct | 1.8700 | 11 |
| KDJ_J | 51.5800 | 39 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 13. `MSFT`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-27（该日共 292 只；全表 15 个日期 / 4237 行）
- Sector：Technology　Price：532.60

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -0.1724 | 33 |
| Momentum_20D_Pct | 4.5913 | 56 |
| Momentum_60D_Pct | 14.6066 | 88 |
| Realized_Volatility_20D_Pct | 19.5722 | 11 |
| Volume_Ratio_20D | 0.9316 | 50 |
| ZScore_20D | 0.5681 | 41 |
| Beta_60D_SPY | 1.4444 | 75 |
| Stock_RS_20D_vs_SPY | 4.6227 | 56 |
| Quant_Score | 30.0000 | 21 |
| MA20 | 527.8700 | 95 |
| MA50 | 509.1700 | 95 |
| ATR_Pct | 2.1200 | 22 |
| KDJ_J | 34.1800 | 29 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 14. `NVDA`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-27（该日共 292 只；全表 15 个日期 / 4237 行）
- Sector：Technology　Price：216.00

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -0.5021 | 30 |
| Momentum_20D_Pct | -5.6192 | 22 |
| Momentum_60D_Pct | 7.5965 | 75 |
| Realized_Volatility_20D_Pct | 30.0557 | 53 |
| Volume_Ratio_20D | 0.8593 | 37 |
| ZScore_20D | -1.0918 | 23 |
| Beta_60D_SPY | 2.0446 | 85 |
| Stock_RS_20D_vs_SPY | -5.5878 | 22 |
| Quant_Score | 74.0000 | 92 |
| MA20 | 224.9000 | 78 |
| MA50 | 222.3000 | 78 |
| ATR_Pct | 2.8300 | 48 |
| KDJ_J | 25.5600 | 25 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Technology）
- N/A（无成交记录）

---

## 15. `GOOGL`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-27（该日共 292 只；全表 15 个日期 / 4237 行）
- Sector：Communication　Price：316.80

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -7.9551 | 5 |
| Momentum_20D_Pct | -7.5711 | 17 |
| Momentum_60D_Pct | -11.0437 | 20 |
| Realized_Volatility_20D_Pct | 21.0658 | 21 |
| Volume_Ratio_20D | 1.0098 | 61 |
| ZScore_20D | -3.0119 | 1 |
| Beta_60D_SPY | 1.3847 | 74 |
| Stock_RS_20D_vs_SPY | -7.5398 | 17 |
| Quant_Score | 22.0000 | 3 |
| MA20 | 341.7900 | 89 |
| MA50 | 342.3600 | 89 |
| ATR_Pct | 2.6300 | 41 |
| KDJ_J | -12.4300 | 0 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Communication）
- N/A（无成交记录）

---

## 16. `AMZN`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-27（该日共 292 只；全表 15 个日期 / 4237 行）
- Sector：Consumer Discretionary　Price：249.09

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -5.0905 | 12 |
| Momentum_20D_Pct | 1.1944 | 39 |
| Momentum_60D_Pct | -8.2812 | 28 |
| Realized_Volatility_20D_Pct | 32.4296 | 61 |
| Volume_Ratio_20D | 0.9105 | 47 |
| ZScore_20D | -0.9304 | 25 |
| Beta_60D_SPY | 1.4824 | 76 |
| Stock_RS_20D_vs_SPY | 1.2257 | 39 |
| Quant_Score | 27.0000 | 14 |
| MA20 | 254.5800 | 82 |
| MA50 | 255.3800 | 82 |
| ATR_Pct | 2.5900 | 40 |
| KDJ_J | -0.3300 | 3 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Consumer Discretionary）
- N/A（无成交记录）

---

## 17. `META`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-27（该日共 292 只；全表 15 个日期 / 4237 行）
- Sector：Communication　Price：630.56

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | -10.6147 | 2 |
| Momentum_20D_Pct | -11.8862 | 10 |
| Momentum_60D_Pct | 13.2654 | 86 |
| Realized_Volatility_20D_Pct | 39.1093 | 74 |
| Volume_Ratio_20D | 1.6028 | 95 |
| ZScore_20D | -2.9380 | 2 |
| Beta_60D_SPY | 1.9263 | 83 |
| Stock_RS_20D_vs_SPY | -11.8549 | 10 |
| Quant_Score | 25.0000 | 7 |
| MA20 | 713.4000 | 97 |
| MA50 | 664.6300 | 97 |
| ATR_Pct | 4.0700 | 82 |
| KDJ_J | -6.1100 | 1 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Communication）
- N/A（无成交记录）

---

## 18. `TSLA`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-27（该日共 292 只；全表 15 个日期 / 4237 行）
- Sector：Consumer Discretionary　Price：391.62

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 6.4011 | 89 |
| Momentum_20D_Pct | 9.5594 | 79 |
| Momentum_60D_Pct | 25.8379 | 95 |
| Realized_Volatility_20D_Pct | 37.7512 | 73 |
| Volume_Ratio_20D | 1.4606 | 92 |
| ZScore_20D | 2.0801 | 89 |
| Beta_60D_SPY | 2.3982 | 89 |
| Stock_RS_20D_vs_SPY | 9.5907 | 79 |
| Quant_Score | 61.0000 | 68 |
| MA20 | 371.5800 | 90 |
| MA50 | 364.7600 | 90 |
| ATR_Pct | 3.4400 | 67 |
| KDJ_J | 87.2800 | 74 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Consumer Discretionary）
- N/A（无成交记录）

---

## 19. `TSM`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-27（该日共 292 只；全表 15 个日期 / 4237 行）
- Sector：N/A　Price：N/A
- 提示：该 ticker 在 2026-10-27 无因子快照

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- N/A（无成交记录）

---

## 20. `BRK-B`

### 1. AI 历史（ai_snapshot.csv）

- 记录数：1

| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |
|---|---|---|---|---|
| 2026-10-02 | Observation | scan | N/A | N/A |

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-27（该日共 292 只；全表 15 个日期 / 4237 行）
- Sector：Other　Price：548.56

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 3.0682 | 62 |
| Momentum_20D_Pct | 9.0381 | 76 |
| Momentum_60D_Pct | 7.2370 | 74 |
| Realized_Volatility_20D_Pct | 10.8609 | 0 |
| Volume_Ratio_20D | 1.0566 | 68 |
| ZScore_20D | 1.8827 | 83 |
| Beta_60D_SPY | -0.1937 | 13 |
| Stock_RS_20D_vs_SPY | 9.0695 | 76 |
| Quant_Score | 71.0000 | 88 |
| MA20 | 520.8600 | 95 |
| MA50 | 511.7100 | 95 |
| ATR_Pct | 1.1800 | 0 |
| KDJ_J | 90.3800 | 79 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Other）
- 样本数：10（按日期倒序展示最近 10 笔）
- **历史同类交易汇总**：共 5 笔，胜率 60.0%，平均盈利 +$248.47，平均亏损 -$310.52，盈亏比 0.80

| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |
|---|---|---|---|---|---|---|
| 2026-10-22 11:30:00 | APA | 卖出 | 48.14 | 200 | 9628.00 | -324.00 |
| 2026-10-19 18:26:47 | APA | 买入 | 49.76 | 200 | 9952.00 | 0.00 |
| 2026-10-16 18:26:27 | ADSK | 卖出 | 237.81 | 43 | 10225.83 | 274.77 |
| 2026-10-14 18:27:00 | ISRG | 卖出 | 414.81 | 24 | 9955.44 | 233.76 |
| 2026-10-13 18:26:54 | ANET | 卖出 | 204.98 | 47 | 9634.06 | -297.04 |
| 2026-10-13 18:26:54 | KR | 卖出 | 60.68 | 168 | 10194.24 | 236.88 |
| 2026-10-07 21:44:58 | ADSK | 买入 | 231.42 | 43 | 9951.06 | 0.00 |
| 2026-10-07 21:44:58 | ANET | 买入 | 211.30 | 47 | 9931.10 | 0.00 |
| 2026-10-07 21:44:58 | ISRG | 买入 | 405.07 | 24 | 9721.68 | 0.00 |
| 2026-10-07 21:44:58 | KR | 买入 | 59.27 | 168 | 9957.36 | 0.00 |

---

## 21. `JPM`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-27（该日共 292 只；全表 15 个日期 / 4237 行）
- Sector：Financials　Price：334.04

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 0.1529 | 35 |
| Momentum_20D_Pct | -0.7576 | 34 |
| Momentum_60D_Pct | -5.0456 | 40 |
| Realized_Volatility_20D_Pct | 13.3768 | 1 |
| Volume_Ratio_20D | 0.8300 | 31 |
| ZScore_20D | 0.1386 | 35 |
| Beta_60D_SPY | 0.3755 | 44 |
| Stock_RS_20D_vs_SPY | -0.7262 | 34 |
| Quant_Score | 32.0000 | 33 |
| MA20 | 333.5700 | 88 |
| MA50 | 344.8300 | 89 |
| ATR_Pct | 1.8700 | 11 |
| KDJ_J | 36.5800 | 30 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Financials）
- N/A（无成交记录）

---

## 22. `V`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-27（该日共 292 只；全表 15 个日期 / 4237 行）
- Sector：Financials　Price：404.16

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 0.3078 | 37 |
| Momentum_20D_Pct | 9.9037 | 81 |
| Momentum_60D_Pct | 10.3870 | 80 |
| Realized_Volatility_20D_Pct | 20.2160 | 14 |
| Volume_Ratio_20D | 0.8898 | 44 |
| ZScore_20D | 1.0099 | 52 |
| Beta_60D_SPY | 0.2993 | 41 |
| Stock_RS_20D_vs_SPY | 9.9351 | 81 |
| Quant_Score | 68.0000 | 84 |
| MA20 | 387.0800 | 91 |
| MA50 | 377.8700 | 91 |
| ATR_Pct | 1.6500 | 3 |
| KDJ_J | 60.8800 | 44 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Financials）
- N/A（无成交记录）

---

## 23. `UNH`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-27（该日共 292 只；全表 15 个日期 / 4237 行）
- Sector：Healthcare　Price：410.70

| 因子 | 值 | 当日百分位 |
|---|---|---|
| Momentum_5D_Pct | 0.9389 | 43 |
| Momentum_20D_Pct | 8.6997 | 72 |
| Momentum_60D_Pct | -0.8929 | 53 |
| Realized_Volatility_20D_Pct | 30.0267 | 53 |
| Volume_Ratio_20D | 0.7580 | 21 |
| ZScore_20D | 1.0868 | 54 |
| Beta_60D_SPY | -0.0765 | 21 |
| Stock_RS_20D_vs_SPY | 8.7310 | 72 |
| Quant_Score | 35.0000 | 45 |
| MA20 | 390.8600 | 92 |
| MA50 | 388.7500 | 92 |
| ATR_Pct | 2.7900 | 47 |
| KDJ_J | 74.8200 | 56 |

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- 该 ticker 无成交记录 → 退化为 同 Sector（Healthcare）
- N/A（无成交记录）

---

## 24. `XOM`

### 1. AI 历史（ai_snapshot.csv）

- N/A（无 AI 快照记录）

### 2. 因子位置（quant_factor_snapshot.csv）

- 快照日期：2026-10-27（该日共 292 只；全表 15 个日期 / 4237 行）
- Sector：N/A　Price：N/A
- 提示：该 ticker 在 2026-10-27 无因子快照

### 3. 交易明细（portfolio_50000_transactions.csv）

- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）
- N/A（无成交记录）

---

说明：只读简报；缺失项统一 N/A。宏观环境在头部统一展示，不重复。
