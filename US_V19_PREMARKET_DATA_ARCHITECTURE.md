# US V19：盘前价格 + 新闻一致性修复

## 核心原则

1. 最后完整常规交易日收盘价（Prev Close）用于日线技术指标。
2. 04:00-09:29 ET 的盘前最新成交（Premarket Price）单独存储，用于当前行情参考。
3. 不允许把盘前价写进日线 Close，也不允许用盘前部分K线污染 MA20/MA50/RSI/MACD/KDJ/ATR。
4. AI 同时看到昨收、盘前价、盘前涨跌幅和盘前时间。
5. 新闻固定本次 Scan 的 as-of 快照时间，并用“上一交易日16:00 ET”把新闻分为“昨收后”与“历史背景”。
6. 期权 underlying spot 优先使用盘前价；若没有盘前价，退回最后完整收盘。

## Yahoo/yfinance依据

yfinance 的 `history(..., prepost=True)` / `download(..., prepost=True)` 支持包含盘前和盘后数据；Yahoo Finance 也明确提供 Extended Hours 展示。

## 目的

避免出现：邮件里显示的是昨收，但用户打开券商看到的是盘前价；或者 AI 把昨收前的旧新闻当成盘前新消息。
