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

## Workflow（10 个）

`scan` · `review` · `evolve` · `dashboard-data` · `news-fetch` · `quant-research` ·
`skill-weekly` · `test` · `_temp-acceleration` · `_temp-test-datasources`

## 快速上手

```bash
python3.12 -m pip install -r requirements-production.txt
PYTHONUTF8=1 python3.12 -m pytest tests/ -q     # 全量回归（必须 3.12）
```

## 文档

- 交接与铁律：`docs/HANDOVER.md`
- 文档索引：`docs/DOCS_INDEX.md`（已归档文档在 `docs/archive/`）
