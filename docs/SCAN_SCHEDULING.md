# Scan 调度、Dashboard 刷新与 Paper 观察期

## 1. 三条时间线不要混为一谈

| 流程 | 触发方式 | 实际职责 | 不能据此推断 |
|---|---|---|---|
| 美股 Scan（`.github/workflows/scan.yml`） | 仅 `workflow_dispatch`；预期由外部调度器触发 | 选股、生成当日 pending、AI Snapshot 与 Quant 价格历史更新 | Dashboard 刷新了，不代表 Scan 已运行 |
| Dashboard Data Refresh（`.github/workflows/dashboard-data.yml`） | GitHub Actions 工作日每 15 分钟 schedule | 刷新 Dashboard 数据；另有既有持仓价格同步与盘中机械止损步骤 | 不会运行 `scan.py`，不代表当天产生了新选股信号 |
| Paper Trading（`.github/workflows/paper-trading.yml`） | Scan 成功后立即登记信号；工作日收盘后另有 UTC 双 cron + 纽约时区门禁 | Scan 运行登记信号/观察日；EOD 任务先刷新完整 OHLCV，再处理当日有效开盘模拟成交与退出、更新日报 | 不允许用旧日开盘价补成交；OHLC 模拟成交不是券商真实回报 |

**唯一业务选股时间点是 Scan 完成并产出当日数据的时间。** Dashboard 页面中的行情刷新时间、Scan 完成时间、EOD 完整行情更新时间和 Paper Trading 观察记录应分别展示，不能用其中一个替代另一个。

Paper Trading 的 Scan 触发只登记信号，不执行买卖；收盘后任务刷新完整日线后才执行。两个 UTC cron 覆盖夏令时与冬令时，任务会检查纽约本地时间，只在 16:00–16:59 ET 执行。错过预期交易日时，订单会过期而不是事后用旧价格成交。

## 2. 外部 Scan 调度监控

`.github/workflows/scan-watchdog.yml` 检查最近的 Scan workflow 运行记录；如果没有近期运行，或最新一次已完成的 Scan 失败，则开一个统一的 GitHub Issue；恢复后在同一个 Issue 留言并关闭。

这只验证 GitHub Actions 中是否出现了运行记录，**并不证明外部调度器本身存在、仍已正确配置或一定按时发送请求**。如果看门狗报警，应同时检查外部任务、GitHub token/权限以及 Scan 最近一次运行结果，而不是直接放宽选股条件。

## 3. 观察期如何计数

`portfolio_paper_observation_dates.csv` 只由 **Scan 成功后自动触发**的 Paper Trading 运行写入，按美东日期记录，包括没有新候选的日期；同一天重复运行只保留一条观察记录。手动触发可用于修复账本/重新生成报告，但明确不增加观察日。日报的 40 日门槛读取该观察日志，不再把价格历史文件中的交易日数当作实际 Scan 观察日数。

如果价格历史不是全量 `phase2b.v2`，模拟成交与未实现盈亏估值会 fail-closed。必须先运行手动的 Rebuild Quant Price History 工作流并通过数据校验；单纯存在新版增量行，不代表旧历史已经修复。

## 4. 安全边界

- `portfolio_paper_transactions.csv` 和观察日志与 `portfolio_50000_*` 实盘账本隔离。
- Paper 成交是根据完整日线重建的模拟价，包含明确标注的滑点/佣金假设，不是券商真实成交回报。
- 调度失效、行情历史缺失或样本不足时，系统应报告“未验证/不可用”，不得把未知结果当成零收益或策略成功。
