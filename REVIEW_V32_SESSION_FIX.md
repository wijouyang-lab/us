# US Review V32 Session-Date Fix

## 这版解决的核心问题

1. Review 不能把美东 00:00-15:59 当成“当天已完成交易日”。
2. 最近已完成常规交易日作为本次 Review 的交易会话日期：
   - 16:00 ET 之后：当天；
   - 16:00 ET 之前：上一交易日；
   - 周末：最近一个工作日。
3. 行情、止损触发、期权 DTE、风险写回、Review history 均采用 `REVIEW_SESSION_DATE`。
4. 因此 GitHub Actions 在 UTC 时间午夜附近运行时，不会再因为美国当地新交易日尚未开盘而出现整份实际持仓“今日开盘→收盘 N/A”。
5. 当日止损只允许使用 `REVIEW_SESSION_DATE` 的完整 OHLC；最近收盘价只用于当前价格跟踪，不会触发止损。
6. 期权 DTE 与正股价格也按最近已完成交易日计算。
7. Wall 的 OI 缺失时仍使用成交量代理，但明确标记为“非OI Wall”，不得误称为真实 OI Wall。
