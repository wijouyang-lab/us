# us —— 美股扫描 / 复盘 / 组合 / 量化研究流水线

宏观驱动的美股候选池扫描、盘中复盘、$50,000 组合账本、期权策略与 Quant Phase 1–7 研究。

## 入口

| 脚本 | 作用 | 由谁驱动 |
|---|---|---|
| `scan.py` | 候选池扫描 + 宏观/情绪 + AI 评分 | `scan.yml` |
| `review.py` | 盘中复盘 + 风控联动 + 组合账本 | `review.yml` |
| `evolve.py` | 策略进化（每月 1 日） | `evolve.yml` |
| `dashboard_export.py` | 生成 `dashboard/data/dashboard_data.json` | `dashboard-data.yml` |
| `quant_research_runner.py` | Quant Phase 2–7 研究（研究态，无生产入口） | `quant-research.yml`（由 `scan.yml` 调用） |

## Workflow 与触发边界

主要入口是 `scan`、`review`、`dashboard-data`、`quant-research`、`evolve` 和纸面组合流程；另有手动触发的一次性历史研究工作流。

- `scan.yml` **仅接收 `workflow_dispatch`**，由仓库外部触发；不要增加 GitHub cron。
- `review.yml` 按工作日计划运行；避免未经授权的手动补跑。
- `dashboard-data.yml` 按工作日每小时刷新；与 Review 共用账本并发组，提交路径有白名单。
- `quant-research.yml` 是研究流水线，由 Scan 调用，也保留手动调试入口；它不是策略激活入口。
- `evolve.yml` 每月 1 日运行；只允许提交明确列出的进化产物。

更完整的触发规则、Phase 2–7 语义、样本成熟度以及生产隔离约束见 `docs/QUANT_LOW_FREQUENCY_OPERATIONS.md`。

## 快速上手

```bash
python3.12 -m pip install -r requirements-production.txt
PYTHONUTF8=1 python3.12 -m pytest tests/ -q     # 全量回归（必须 3.12）
```

## 文档

- 交接与铁律：`docs/HANDOVER.md`
- 文档索引：`docs/DOCS_INDEX.md`（已归档文档在 `docs/archive/`）
