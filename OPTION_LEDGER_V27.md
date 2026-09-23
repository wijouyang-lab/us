# V27 期权账本修复

- `trade_history.csv` 是股票 Scan/Review 账本，不写期权字段。
- `option_strategies.csv` 是期权策略账本，Scan 生成策略时写入。
- 旧版 Scan workflow 只提交 `us_stocks_pending_*.csv`，没有提交 `option_strategies.csv`；GitHub Actions runner 结束后，该文件不会保留到下一次 Review。
- V27 让 Scan workflow 提交 `option_strategies.csv`，Review workflow 也提交它的状态变化。
- Review 本身已经有 `build_option_review_html(...)`；真正缺的是跨 workflow 的期权账本持久化。
