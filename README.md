# US Review KPI 修复

运行方式：在美股仓库根目录执行 `python review_kpi_tracking_fix.py`。

它只修改 `review.py` 的 KPI 统计区，不改 Scan 逻辑。

修复后：
- Scan 的 Observation 推荐也参与涨跌幅追踪；
- 当前推荐跟踪胜率 = 实际持仓 + Observation；
- Scan推荐综合胜率 = 持仓 + Observation + 已了结股票；
- 总股票推荐笔数包含 Observation；
- 股票 KPI 与期权 KPI 分开，避免期权收益污染股票推荐胜率；
- Observation 会记录 `推荐跟踪涨跌幅(%)`。
