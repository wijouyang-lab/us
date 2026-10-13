# Review 精简 + quant-research 链式化 + 激活 flag —— 实施报告

> 时间：2026-10-09 晚
> 铁律遵守：未改 `process_buys`/`process_sells`、未改 `scan.py` 主逻辑、未改 `review.py`/`review.yml`、
> 未改 `portfolio_50000.py` 的 `run()`、未碰监控。仅改 **前端（app.js）** + **2 个 workflow**。

---

## 1. 三个 commit SHA

| # | commit | 内容 |
|---|---|---|
| 1 | **`4e94298`** | `feat(dashboard): simplify review tiles (drop obs/options)` |
| 2 | **`7ec5085`** | `ci: run quant-research after scan (needs: scan)` |
| 3 | **`dcc4e4a`** | `ci: enable AI target holdings flag` |

推送范围：`5c260f4..dcc4e4a main -> main`（rebase 远端 `edba8e7..5c260f4` 后干净变基，无冲突）。

**改动文件（3 commit 累计，仅 3 个）**：

| 文件 | 改动 |
|---|---|
| `app.js` | `renderReview` 删 3 tile + Core 胜率样本门限（+4/−4） |
| `.github/workflows/scan.yml` | 新增 `quant-research` job（`needs: scan`）+ env 加 `ENABLE_TARGET_FILE: "1"`（+10） |
| `.github/workflows/quant-research.yml` | `on:` 去掉 cron TBD、加 `workflow_call`（+1/−3） |

> **硬证据**：`git diff --name-only 5c260f4..HEAD | grep -E "review.yml|portfolio_50000.py|scan.py"` → **空**（三者均未被触碰）。

---

## 2. 全量测试结果

```
281 passed, 7 warnings in 11.92s
```

- 基线 281（267 + 盘中止损 14）→ 本次纯前端/YAML 改动**不改动 Python**，仍 **281 passed**，满足 ≥281。
- 7 个 warning 为既有 `datetime.utcnow()` 弃用告警（quant_production.py），与本次无关。
- `node --check app.js` → **JS OK**。
- 两个 workflow YAML `yaml.safe_load` → **YAML OK**。

**任务 1 前端 headless 渲染验证（抽取 app.js 真实 `reviewTile`/`renderReview` 源码，隔离 vm 执行）**：

```
✓ 保留: Core Closed
✓ 保留: Core Open
✓ 保留: Actual Active
✓ 保留: Stop Loss 触发
✓ 保留: Core 胜率
✓ 已删: Obs Closed
✓ 已删: Obs Open
✓ 已删: Active Options
✓ 样本<10 → 显示「数据不足」   （样本=4）
结果: PASS
```

---

## 3. 明早 review 安全性确认（硬证据）

明早 06:23（北京）跑的是 **review.yml → `python review.py` + `python portfolio_50000.py --data-dir .`**。
本次 3 个 commit 对它**零影响**，逐条硬证据：

| # | 证据 | 结论 |
|---|---|---|
| 1 | `review.yml` 不在改动文件清单（`git diff --name-only 5c260f4..HEAD` 无 review.yml） | review 工作流定义未变 |
| 2 | `portfolio_50000.py` 不在改动文件清单 | review 的 `--data-dir .` 命令路径未变；`run()` 未动 |
| 3 | `scan.py` 不在改动文件清单 | review 依赖的脚本未变 |
| 4 | 本次改的 `scan.yml` 只影响 **scan 工作流**（`workflow_dispatch` 触发），与 review.yml 是**两个独立 workflow**，无 `needs`/无交集 | review 触发链不受影响 |
| 5 | `quant-research.yml` 的 `workflow_call` 只被 `scan.yml` 的 `quant-research` job 调用（`needs: scan`）；review.yml 未引用它 | review 不会拉起 quant-research |
| 6 | `ENABLE_TARGET_FILE` 仅在 `scan.yml` 的 scan job env 生效；review 不读该变量、不写 target 文件 | review 数据面无变化 |

**一句话**：3 个 commit 全部落在「scan 工作流 + 前端」两侧，review 走的是完全独立的 review.yml + `portfolio_50000.py --data-dir .`（未动），明早 review 行为与改前**逐字节一致**。

---

## 4. 下周一预期行为

1. **scan 触发**（`workflow_dispatch` 手动）→ 依次跑 `scan.py` → `quant_factor_price.py` → 提交。
2. **消费 ENABLE_TARGET_FILE flag（新）**：`scan.py` 首次写出 `portfolio_50000_target.csv`（AI 目标持仓）→ `dashboard_export.py` 读入 `portfolio.target` → 前端 `#targetCard` 显示「AI 目标持仓」卡片（`renderTarget` 早已就绪，本次只是打开 flag）。
3. **quant-research 链式触发（新）**：scan job 成功后，`quant-research` job（`needs: scan`）自动跑 Phase 2-7 研究管道（`quant_research_runner.py`），产出研究工件并 `[skip ci]` 提交。**不再依赖 cron TBD**——之前注释态永不触发、攒 70 天也白等，现已由 scan 每日驱动。
4. **review 依旧独立**：下周一盘后 review 照常，不受以上任何一步影响。

> 注：quant-research 内已有 `Guard - require snapshot`（无 `quant_factor_snapshot.csv` 时 skip 不报错）；scan 会先产出该 snapshot，故链接后可正常执行。

---

## 5. 前端截图（Review 板块精简后）

见同目录 `review_tiles_simplified.png`（用 app.js 中**真实** `reviewTile`/`renderReview` 源码渲染）。

**第一行**：Core Closed(4) · Core Open(2) · Actual Active(5)
**第二行**：Stop Loss 触发(1) · Core 胜率(**数据不足** —— 样例样本仅 4 笔 < 10，按新门限显示占位)
**已消失**：Obs Closed · Obs Open · Active Options

---

## 6. 附：与铁律的对应

| 铁律 | 状态 |
|---|---|
| 不改 `process_buys`/`process_sells` | ✅ 未触碰 |
| 不改 `scan.py` 主逻辑 | ✅ 未触碰 `scan.py` |
| 不改 `review.py`/`review.yml` | ✅ 未触碰 |
| 不改 `portfolio_50000.py` 的 `run()` | ✅ 未触碰该文件 |
| 不碰监控 | ✅ 未触碰 |
| 只改前端 + scan.yml + quant-research.yml | ✅ 实际改动仅 app.js + 2 个 workflow |
| rebase 冲突立即停下报告 | ✅ rebase 无冲突（干净变基成功） |
