# 低频量化项目：运行与验收准则

本文说明当前仓库中 Scan、Review、Dashboard 与 Quant Phase 2–7 的实际责任边界。这里记录的是**当前代码契约**，不是旧报告中的历史运行时间表。

## 1. 触发规则

| 工作流 | 触发方式 | 运维边界 |
|---|---|---|
| `.github/workflows/scan.yml` | 只有 `workflow_dispatch` | 由仓库外部调度器触发。GitHub 不会自行定时启动 Scan；不要加 cron。 |
| `.github/workflows/review.yml` | `workflow_dispatch` + 工作日 cron `23 22 * * 1-5` UTC | 写 Review / 风控 / 账本结果；不要未经授权补跑生产 Review。 |
| `.github/workflows/dashboard-data.yml` | 工作日每小时 `0 * * * 1-5` UTC、手动触发、限定路径的 main push，以及 Scan 成功结束后的 `workflow_run` | 与 Review 使用同一账本并发组；Scan 失败不触发跟随刷新；导出器和日志管道失败都必须使步骤失败。 |
| `.github/workflows/quant-research.yml` | `workflow_dispatch` + `workflow_call` | Scan 后执行研究 Phase 2–7；没有独立 cron。 |
| `.github/workflows/evolve.yml` | 手动触发 + 每月 1 日 `0 2 1 * *` UTC | 只提交策略进化明确允许的文件；不得全量暂存 runner 工作目录。 |
| `paper-trading.yml` | 手动触发或 Scan 成功后的工作流事件 | 纸面组合；不是券商实盘下单接口。 |

一次性历史回填 / PIT 研究工作流是独立研究工具。不得将其与生产 Scan、Review 或 Evolve 混为一谈。

## 2. Quant Phase 2–7 的含义

- **Phase 2 — Backtest**：消费真实 Factor Snapshot 和持久化价格历史，计算 T+5 / T+10 / T+20 前瞻收益。未来价格不存在时必须保留缺失值，不能插值或用旧价格替代。
- **Phase 3 — Validation**：生成研究证据，不自动批准因子。
- **Phase 4 — Score V2**：生成候选模型/因子注册信息；候选不等于生产批准。
- **Phase 5 — Walk-Forward**：按 `Technical_Date` 的真实日期构造训练 / OOS 窗口。当前配置使用 50 个训练日期、20 个 OOS 日期步长；第一窗口至少需要约 **70 个不同的有效日期**。重复股票行数不等于日期样本量。窗口数量不足时应保持 `NOT_ENOUGH_DATA`，不能降低门槛来制造绿灯。
- **Phase 6 — Shadow**：默认禁用；`SHADOW_ENABLE=False` 时，运行状态不能被解释为已完成线上 Shadow 验证。
- **Phase 7 — Production Governance**：评估治理状态、写入 state / audit。状态为 `READY_FOR_PRODUCTION` 仍不等于模型已启用；必须有独立人工批准。

生产基线仍是现有 Quant Score V1。候选结果、历史 IC 报告、单次回测收益或成功的 CI 都不能单独触发 Quant V2。

## 3. 研究数据成熟度与价格源失败

运行后检查这些产物，而不是依赖过期报告中的日期或状态：

- `quant_research_status.json`：各阶段运行状态、写入状态、原因；
- `quant_factor_validation_report.json`：各 horizon 的样本成熟度、因子状态和冗余；
- `quant_walk_forward_summary.json`：窗口数、OOS 样本和模型状态（仅在产生有效结果时更新）。

`quant_factor_price.py` 的批量抓价为空时返回 `FETCH_EMPTY`：保留现有价格历史，不覆盖旧文件、不创建表头空文件，并在 Actions 中发 warning。该研究抓价失败不应阻断一次有效的 Scan / Pending 写入；相应的未来收益标签仍应保持缺失，不能假报为已刷新。

生产实时 Factor Snapshot 与 `research_*` 历史实验数据是不同数据层。不要把回填价格当成历史因子快照，也不要把研究版 PIT 输出直接复制到生产 Quant 文件中以绕过成熟度检查。

## 4. 改动验收要求

1. Scan 触发契约保持外部调用，不添加 GitHub cron。
2. 不降低 Phase 3 样本 / 证据阈值，不降低 Phase 5 训练或 OOS 门槛。
3. 不自动设置 `QUANT_SCORE_V2_ENABLED`、`SHADOW_ENABLE` 或人工批准字段。
4. 不在 CI、回归测试或研究回填中运行真实生产 Scan / Review / Evolve，也不发送生产邮件。
5. 所有新路径行为都应增加回归测试；不得用全量 `git add -A` 或 force push 来提交产物。
6. 全量 Python 回归使用 Python 3.12：

```bash
PYTHONUTF8=1 python3.12 -m pytest tests/ -q
```

## 5. 近期数据检查的解释

Live snapshot 日期数可能随真实扫描逐日增长，因此任何固定日期 / 固定行数结论很快会过期。判定 Quant 是否 ready，应以最近一次成功的状态 JSON、当前有效 `Technical_Date` 数以及 horizon 的成熟度为准。**CI 通过代表代码通过测试，不代表 OOS 证据已经成熟，也不代表模型获准进入生产。**
