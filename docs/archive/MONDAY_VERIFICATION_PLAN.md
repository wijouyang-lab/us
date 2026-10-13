# 周一验证计划 (MONDAY VERIFICATION PLAN)

> 生成日期：2026-10-10 ｜ 仓库：`us-market-terminal` ｜ 当前 `HEAD = 2c24885`（= `origin/main`）
> 用途：周一四个时点逐一核对新功能是否按预期运行，并在异常时按本文快速回滚。

---

## 0. 背景：本轮已上线的新功能（周一重点盯防）

| 功能 | 关键改动文件 | 门控方式 | 相关 commit |
|---|---|---|---|
| #1 买入侧冷却 | `portfolio_50000.py` | 逻辑变更（**无 flag**） | `ce3ad32` |
| AI 原因回填 | `review.py` | flag `ENABLE_AI_REASON_BACKFILL=1`（**默认关**） | `42b6f9e` |
| #3 持仓进池 | `quant_filter.py`（零逻辑，仅补测试） | — | `119af4d`（与 #4 合并提交） |
| #4 浮动只数 + 百分比仓位 | `portfolio_50000.py` / `quant_filter.py` / `dashboard_export.py` / `app.js` | 逻辑变更（**无 flag**） | `119af4d` `a29e9b8` `2c24885` |
| AI Target 持仓面板 | `scan.py` / `dashboard_export.py` / `app.js` | flag `ENABLE_TARGET_FILE=1`（**默认关**） | `a9b1cf8` `ca701c6` `4edf1b7` `dcc4e4a` `d986931` |
| 盘中止损 | `portfolio_50000.py` | CLI `--intraday-stop`（见 `dashboard-data.yml:92`） | `83152b7` |

**Workflows**：`review.yml` · `scan.yml` · `dashboard-data.yml` · `quant-research.yml` · `news-fetch.yml` · `evolve.yml`

> ⚠️ 关键设计：**#4 的 `unit_dollars_for` 在 `AI_Score` 缺失时退化为固定 1 Unit**（向后兼容，见 `portfolio_50000.py`）。因此 `quant-research` 失败不会让 `scan` 崩溃。

---

## 1. 周一验证时间线

| 北京时点 | 触发 Workflow | 性质 |
|---|---|---|
| **06:23** | `review.yml` | 盘前 review 检查点 |
| **21:07** | `scan.yml` | 盘后 scan 检查点 |
| **21:30+** | `dashboard-data.yml`（每 15 分钟） | Dashboard 刷新检查点（含 `--intraday-stop` / `--price-only` 步骤） |
| **22:00** | `review.yml` | 盘后 review 检查点 |

---

## 2. 每个时点的检查项

### 06:23 — review 检查点
- **看什么**：GitHub Actions → `review.yml` 是否 green；线上 Dashboard 是否刷新出当日 review 结论；`trade_history.csv` 末行时间戳是否更新。
- **期望**：review 成功退出；`AI_Score` 正常落库（pending 行被评分并清除 `Pending_Reason`）；无 traceback。
- **异常看哪**：`review.yml` 运行日志；`review.py` 报错栈；`trade_history.csv` 末 5 行；若误开 `ENABLE_AI_REASON_BACKFILL`，看 `review.py:3820` 附近日志（该逻辑已 try/except 包裹，不应影响主流程）。

### 21:07 — scan 检查点
- **看什么**：`scan.yml` 是否 green；是否产出新推荐/候选；`portfolio_50000_target.csv`（**仅当 `ENABLE_TARGET_FILE=1`**）；scan pending 行的 `AI_Score` 是否写入。
- **期望**：scan 成功；候选入池且**持仓优先不被截断**（#3 / #4 Diff D）；若开启 target，文件为合法 CSV（含 `Ticker`/`Price`/`Units` 等列）。
- **异常看哪**：`scan.yml` 日志；`scan.py:3957` 附近（target 写点）；`portfolio_50000_target.csv` 表头；`quant_filter.build_ai_input` 是否抛错。

### 21:30+ — Dashboard 检查点
- **看什么**：`dashboard-data.yml` 多次运行 green；线上页面 **50k 持仓 / Quant section / Target card（若开）/ News / Runtime** 全部渲染；浏览器控制台无 JS 报错；持仓只数与股票占比显示合理（3–5 只）。
- **期望**：页面无白屏；`open_pct` 透传正确；`--intraday-stop` 步骤在盘前/盘后静默退出、**未产生非预期 SELL**。
- **异常看哪**：`dashboard-data.yml` 日志（尤其 `:86 --price-only`、`:92 --intraday-stop`）；浏览器 Console；`dashboard_export.py:2543`（target 读点）；`app.js` 语法。

### 22:00 — review 检查点
- **看什么**：第二次 `review.yml` green；盘后最终 review 完整；`transactions.csv` 末行（是否有当日买卖/止损决策）。
- **期望**：与 06:23 一致；review 写入完整；#1 冷却字段 `Cooldown_Until` 在止损后被正确写入。
- **异常看哪**：`review.yml` 日志；`transactions.csv` 末 5 行；`portfolio_50000_positions.csv` 的 `Cooldown_Until` 列。

---

## 3. 应急预案

- **scan job 失败 → 回滚**：先确认根因。若是 #4 Diff D（`build_ai_input` 截断/抛错）→ `git revert 119af4d` 后重跑 scan；若是 target 写点异常 → 先关 flag（见下）；通用情况直接在 Actions 页面手动 re-run `scan.yml`。
- **quant-research 失败 → 会不会影响 scan**：**不影响 scan 运行**。两 workflow 互相独立；scan 读取量化分数失败时走 #4 的 fallback（`AI_Score` 缺失 → 固定 1 Unit），仅仓位缩放失效、不会崩。修复方向是单独排查 `quant-research.yml`，**不阻塞 scan**。
- **target 文件格式错 → 关闭 flag**：在 `dashboard-data.yml` / `scan.yml` 的运行 env 中**移除 `ENABLE_TARGET_FILE=1`**（默认即关）。scan 不再写 `portfolio_50000_target.csv`、dashboard 不再读，Target card 自动隐藏。**无需 revert 代码**。
- **盘中止损误触发（无故多笔 SELL）→ 关掉该步骤**：编辑 `dashboard-data.yml` **第 92 行**，删除 `--intraday-stop` 参数（改为 `python portfolio_50000.py --data-dir .` 或仅 `--price-only`），提交即可。该步骤默认不进主流程，无需 revert `83152b7`。

---

## 4. 一键回滚命令

> 原则：**能关 flag / 改 workflow 就不 revert 代码**；revert 一律用 `git revert`（产生新提交、不改写历史，符合铁律）。revert 多个 commit 时按**从新到旧**顺序给出。

| 功能 | 软关闭（首选，零代码改动） | 硬回滚（git revert） |
|---|---|---|
| AI Target 面板 | 移除 `ENABLE_TARGET_FILE=1`（在 `dashboard-data.yml` / `scan.yml` 的 env 中，默认关） | `git revert d986931 dcc4e4a 4edf1b7 ca701c6 a9b1cf8` |
| AI 原因回填 | 确保 `ENABLE_AI_REASON_BACKFILL` 未设置（默认关，且未进任何 workflow） | `git revert 42b6f9e` |
| #3 + #4（持仓进池 + 浮动只数/百分比） | 无 flag，只能硬回滚 | `git revert 2c24885 a29e9b8 119af4d` |
| #1 买入冷却 | 无 flag，只能硬回滚 | `git revert ce3ad32` |
| 盘中止损 | 删 `dashboard-data.yml:92` 的 `--intraday-stop` | `git revert 83152b7` |

回滚后统一：`git push origin main`，再到 Actions 手动 re-run 受影响的 workflow。

---

## 5. 判断矩阵（异常 → 动作）

| 异常现象 | 可能根因 | 对应动作 |
|---|---|---|
| `review.yml` 红 + 栈在 `review.py` | review 逻辑 / API 限流 | 看日志定位；若 `ENABLE_AI_REASON_BACKFILL` 误开 → 关；否则 re-run |
| `scan.yml` 红 + 候选为空 / 持仓被截断 | #4 Diff D 改坏 `build_ai_input` | `git revert 119af4d` → 重跑 scan |
| `scan.yml` 红 + "target 格式" 报错 | `ENABLE_TARGET_FILE` 开 + 写坏 | 移除 `ENABLE_TARGET_FILE=1`（软关） |
| Dashboard 白屏 / Console JS 报错 | #4 Diff E `app.js` 字段或语法 | `git revert 2c24885`（或先查 `app.js`） |
| 线上持仓只数恒 >5 或持续 <3 | #4 浮动逻辑异常 | `git revert 2c24885 a29e9b8 119af4d` |
| 无故多笔 SELL（未触止损线） | 盘中止损误触发 | 删 `dashboard-data.yml:92` 的 `--intraday-stop` |
| `AI_Score` 全空 / 仓位恒为 1 Unit | `quant-research` 失败 | scan 仍可用（fallback）；单独修 `quant-research.yml` |
| 止损后次日又买入同一票 | #1 冷却失效 | `git revert ce3ad32` |
| `trade_history` 末行时间戳未更新 | workflow 未按计划触发 | 检查 Actions 调度 / cron；手动 re-run |

---

*附：本文所有 commit SHA 与行号均取自 `HEAD = 2c24885`，如后续有新提交请以 `git log` 为准。*
