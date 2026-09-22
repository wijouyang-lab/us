# V22 Observation 最新价格独立追踪修复

## 修复原因
Review 原先的 Observation 当前价依赖 `price_map_today`，而 `price_map_today` 主要由 `recent_picks` 的持仓账本行情池构建，并且优先寻找“今天日期”的日线。如果某个 Observation 没有命中该行情池或当天没有精确日线，就会显示 `N/A`。

## 新逻辑
1. 先从 Scan 推荐事件账本收集最近 30 天全部 Core + Observation ticker。
2. 独立批量抓取最近 7 个交易日的完整日线收盘价，使用未复权 Close。
3. 个别 ticker 失败时逐只 `Ticker.history()` 补抓。
4. 再失败才使用 `fast_info.last_price`，并标记为 `Yahoo FastInfo 兜底`。
5. 刷新 `price_map_today` 后重新构建 Scan 事件账本。
6. Observation 使用独立事件行情，不再依赖是否为真实持仓。
7. Observation 邮件增加 `当前价格来源` 与 `数据日期`。

## 绩效口径
- 当前开放推荐：使用最近一个有效市场价格计算浮动 PnL。
- 已结束推荐：优先使用真实退出价格，不使用当前价格反算历史已实现 PnL。
- Observation：不是持仓，但必须持续跟踪最新价格，并在事件结束后进入 Observation 已完成统计。
