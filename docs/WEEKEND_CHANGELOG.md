# 周末变更记录（WEEKEND CHANGELOG）

> 生成日期：2026-10-10 23:18（GMT+8）｜ 仓库：wijouyang-lab/us ｜ 分支：`main`
> 覆盖范围：**2026-10-09 晚 ~ 2026-10-10 全天** 的全部人工提交。
> 当前 `HEAD = 683b45b`（= `origin/main`），工作树 clean。

---

## 0. 数量说明

> 用户原估「10 个 commit」。实际周末**人工（WorkBuddy）提交共 17 个**，另有 **108 个 `github-actions[bot]` 的 `chore(dashboard): refresh market data [skip ci]`** 自动数据刷新提交（纯噪声，不计入功能变更，已排除）。
> 下文 §1 完整列出 17 个人工提交；§2 按模块归类。

---

## 1. 周末 Commit 清单（17 个人工提交）

| # | SHA（短） | 日期 | Message | 影响文件 |
|---|---|---|---|---|
| 1 | `605559ca` | 10-09 | feat(quant): expand price history to OHLCV | `quant_factor_price.py`, `quant_factor_price_history.csv`, `tests/test_quant_factor_price.py` |
| 2 | `a74fdd4b` | 10-10 | fix(quant): keep price-history schema_version v1 (additive column change) | `quant_factor_price.py` |
| 3 | `d4af5491` | 10-10 | docs(quant): fix stale comment (schema kept at v1) | `quant_factor_price.py` |
| 4 | `933848ca` | 10-10 | fix(ci): add push retry to quant-research (prevent data loss) | `.github/workflows/quant-research.yml` |
| 5 | `d9869314` | 10-10 | fix(ci): commit target file + enable flag in dashboard-data | `.github/workflows/dashboard-data.yml`, `.github/workflows/scan.yml` |
| 6 | `b7003d5` | 10-10 | fix(ci): guard transactions.csv add in dashboard-data | `.github/workflows/dashboard-data.yml` |
| 7 | `3aff4c75` | 10-10 | feat(news): add market_relevant field to AI translation | `dashboard/fetch_news.py`, `tests/test_fetch_news.py` |
| 8 | `b3e35a4` | 10-10 | feat(dashboard): filter non-market-relevant news items | `app.js`, `tests/test_news_frontend_filter.py` |
| 9 | `3ba1ceb0` | 10-10 | feat(dashboard): add stopped-out positions panel | `app.css`, `app.js`, `index.html`, `tests/test_quant_dashboard.py`, `tests/test_stopped_frontend.py` |
| 10 | `d1c7325f` | 10-10 | fix(dashboard): render intraday-stop banner (scope bug) | `app.js`, `tests/test_intraday_stop_frontend.py` |
| 11 | `ce3ad32` | 10-10 | feat(portfolio): add cooldown after stop-loss (no rebuy same day/next day/7d) | `portfolio_50000.py`, `tests/test_buy_cooldown.py` |
| 12 | `42b6f9e9` | 10-10 | feat(review): backfill pending stop-loss reasons via AI (flag-gated, default off) | `review.py`, `tests/test_review_reason_backfill.py` |
| 13 | `119af4d2` | 10-10 | feat(quant-filter): #3 持仓优先回归 + #4 Diff D 候选动态数 | `quant_filter.py`, `tests/test_quant_filter.py` |
| 14 | `a29e9b8` | 10-10 | feat(portfolio): #4 浮动只数 + 百分比仓位（核心逻辑） | `portfolio_50000.py`, `tests/test_portfolio_50000.py` |
| 15 | `2c24885` | 10-10 | feat(dashboard): #4 Diff E 显示口径（浮动只数 + 百分比） | `app.js`, `dashboard_export.py` |
| 16 | `df560863` | 10-10 | ci: enable AI reason backfill in review | `.github/workflows/review.yml` |
| 17 | `683b45b` | 10-10 | feat(quant-filter): lower MIN_SCORE from 90 to 80 (90 was above physical score cap 87) | `quant_filter.py`, `tests/test_quant_filter.py` |

---

## 2. 按模块分类

| 模块 | 改动 | 相关 commit |
|---|---|---|
| **portfolio_50000.py** | **冷却**：止损后 `Cooldown_Until` 写入（当日/次日/7d 三层禁买），无 flag，逻辑变更｜**浮动只数 + 百分比仓位**：删 `MAX_OPEN_POSITIONS` 守卫、动态 `unit_dollars_for`、新增 `_within_alloc`（单只≤25%/总股票≤80%）｜**盘中止损**：代码侧由更早的 `83152b7` 提供，周末仅通过 `dashboard-data.yml --intraday-stop` 驱动（见 workflows 行） | `ce3ad32`, `a29e9b8` |
| **quant_filter.py** | **MIN_SCORE 90→80**：评分物理上限稳定 86–87，90 永远筛不出候选→候选功能失效｜**候选动态数**：`min(3, 7-持仓数)` 取代固定候选数（#4 Diff D）｜#3 持仓优先回归测试补足 | `683b45b`, `119af4d2` |
| **review.py** | **AI 原因回填**：pending 止损行经 AI 补 `Stop_Reason`，`ENABLE_AI_REASON_BACKFILL=1` 默认关，已 try/except 包裹不影响主流程 | `42b6f9e9` |
| **app.js / app.css** | **已止损板块面板**：`renderStoppedOut` + `index.html` 卡片（`3ba1ceb0`）｜**盘中止损横幅**：修 `renderIntradayStops` 作用域死代码（`d1c7325f`）｜**market_relevant 新闻过滤**：非市场相关新闻前端隐藏（`b3e35a4`）｜**#4 Diff E 显示口径**：浮动只数 + 百分比（`2c24885`） | `3ba1ceb0`, `d1c7325f`, `b3e35a4`, `2c24885` |
| **dashboard/fetch_news.py** | **market_relevant 字段**：AI 翻译产出市场相关性标记，供前端过滤 | `3aff4c75` |
| **dashboard_export.py** | **open_pct 透传**：#4 仓位百分比经 `open_pct` 注入前端展示口径 | `2c24885` |
| **workflows** | **flag 注入**：`review.yml` 注入 `ENABLE_AI_REASON_BACKFILL`（`df560863`）｜**AI 目标文件 + 盘中止损驱动**：`dashboard-data.yml` + `scan.yml` 启用 `ENABLE_TARGET_FILE` 与 `--intraday-stop`（`d9869314`）；`dashboard-data.yml` 增加 `transactions.csv` 提交保护（`b7003d5`）｜**quant-research 挂载 + push 重试**：防数据丢失（`933848ca`） | `df560863`, `d9869314`, `b7003d5`, `933848ca` |
| **quant_factor_price.py / history** | **OHLCV 扩展**：price history 扩列为 OHLCV，但 `schema_version` 保持 v1（additive 变更），旧读取兼容（`605559ca`, `a74fdd4b`, `d4af5491`） | `605559ca`, `a74fdd4b`, `d4af5491` |

---

## 3. 回滚路径

> 原则：**能关 flag / 改 workflow 就不 revert 代码**；revert 一律 `git revert`（产生新提交，不改写历史，符合铁律）。多个 revert 按**从新到旧**顺序给出。详细判断矩阵见 `archive/MONDAY_VERIFICATION_PLAN.md` §4–§5。

| 改动 | 关闭方式（首选，零代码改动） | 硬回滚（git revert，产生新提交） |
|---|---|---|
| **AI 原因回填** | 删除 `review.yml` 的 `ENABLE_AI_REASON_BACKFILL`（默认即关，未设置即无效） | `git revert 42b6f9e9`（代码）＋ `git revert df560863`（yml flag） |
| **盘中止损** | 删除 `dashboard-data.yml` 第 92 行的 `--intraday-stop` 参数 | `git revert d9869314`（周末启用点）；更早代码 `83152b7` 可不动（flag 关即不进主流程） |
| **AI 目标持仓** | 删除 `scan.yml` / `dashboard-data.yml` 的 `ENABLE_TARGET_FILE=1`（默认关） | `git revert d9869314`（`scan.yml` + `dashboard-data.yml` 启用点） |
| **MIN_SCORE 90→80** | 无 flag，只能硬回滚 | `git revert 683b45b` |
| **浮动只数 + 百分比仓位** | 无 flag，只能硬回滚 | `git revert 2c24885 a29e9b8 119af4d2`（#4 Diff E/D + 核心逻辑 + 候选动态数） |
| **买入冷却** | 无 flag，只能硬回滚 | `git revert ce3ad32` |

回滚后统一：`git push origin main`，再到 Actions 手动 re-run 受影响 workflow。

---

## 4. 已知技术债

> 引用本地模拟报告（`sim_monday_scan.py`、`/tmp/sim_monday_scan.py` 跑真实 `strict_filter`/`build_ai_input` 的结论）的 Bonus B / C / D。

### Bonus B — CSV vs 内存字段名不一致
`portfolio_target.py` 的内存行（`build_portfolio_target_rows` 产出的 dict）与最终写出的 `portfolio_50000_target.csv` 表头**字段命名/口径存在错位**：部分列在内存里用一套 key，落盘时因 DictWriter 字段映射不同，下游 `dashboard_export.py` 按表头读取时拿到空值或错位值。属「写盘层与消费层契约」未固化问题，需统一字段名并加 schema 断言。**本轮未修（留待后续），仅记录。**

### Bonus C — target HOLD 行 `Stop_Loss` 空（本次已修）
`build_portfolio_target_rows` 的 **HOLD 行 `Stop_Loss` 为空**——根因是 snapshot 数据里**没有 `Stop_Loss` 列**，而真实止损价实际躺在 `portfolio_50000_positions.csv` 的 `Stop_Loss` 列。
> ✅ **已在本轮任务 B 修复**：`portfolio_target.py` 复用既有 `_load_held_shares()` 的持仓 CSV 读取路径，从 `portfolio_50000_positions.csv` 读取 `Stop_Loss` 回填 HOLD 行；BUY 行逻辑不变（仍从 snapshot/候选行取，为空也接受）；持仓 CSV 缺失时不影响。详见任务 B 的 commit diff。

### Bonus D — 组合已近 80% 天花板
#4 浮动只数 + 百分比仓位上线后，组合总股票仓位已逼近 **80% 硬顶**（来自 `OPTIONS_WHEEL_DESIGN.md` §1.3 与 `WEEKEND_IMPLEMENTATION_PLAN.md` 四维占比预审）。后果：
- 可用加仓空间极小，新候选即使评分达标也难开仓；
- 触发「满仓(=80%)→评分≥最差+20 换股」分支，而非直接加仓；
- 与期权 wheel（L2 需占用现金担保）存在资源竞争——**这是 wheel 延后 3 个月启动的底层约束之一**。
> 属结构性约束，非 bug；周一需盯「线上持仓只数是否恒 >5 或持续 <3」作为异常信号（`archive/MONDAY_VERIFICATION_PLAN.md` §5）。

---

## 5. 周一验证清单

> 完整脚本与逐时点检查见 `monday_check.sh`（8 项只读检查，✅/❌/⚠️）与 `archive/MONDAY_VERIFICATION_PLAN.md`。以下为浓缩版。

### 5.1 四个关键时点（北京时区）
| 北京时点 | 触发 Workflow | 性质 | 重点盯防 |
|---|---|---|---|
| **06:23** | `review.yml` | 盘前 review | 06:23 green；`trade_history` 末行时间戳更新；`AI_Score` 落库；误开 `ENABLE_AI_REASON_BACKFILL` 时看 `review.py` 日志（应被 try/except 兜住） |
| **21:07** | `scan.yml` | 盘后 scan | scan green；候选入池且持仓优先不被截断（#4 Diff D）；`portfolio_50000_target.csv` 仅当 flag 开才产出 |
| **21:30+** | `dashboard-data.yml`（每 15 分钟） | Dashboard 刷新 | 页面无白屏；`open_pct` 透传正确；`--intraday-stop` 盘前/盘后静默退出、未产生非预期 SELL；浏览器 Console 无 JS 报错 |
| **22:00** | `review.yml` | 盘后 review | 第二次 green；`Cooldown_Until` 在止损后被正确写入；`transactions.csv` 末行有当日决策 |

### 5.2 `monday_check.sh` 覆盖的 8 项检查
1. review 流程可跑（无 traceback）
2. scan 流程可跑（无 traceback）
3. target 文件合法（若开 flag）
4. quant 分数可用（MIN_SCORE=80 后候选数应 >0 或合理为 0 不崩）
5. news 数据完整（顶层 `market_news` + `error` 键，无 0+error 误报）
6. 冷却字段写入（`Cooldown_Until`）
7. 盘中止损步骤静默（无意外 SELL）
8. 距下次调度倒计时（天/时/分三级进位）

### 5.3 周一异常 → 动作速查（详见 `archive/MONDAY_VERIFICATION_PLAN.md` §5）
- scan 红 + 候选空/持仓截断 → `git revert 119af4d2` 重跑
- 止损后次日又买同票 → `git revert ce3ad32`
- 无故多笔 SELL → 删 `dashboard-data.yml:92 --intraday-stop`
- Dashboard 白屏/JS 错 → `git revert 2c24885` 或先查 `app.js`
- 持仓只数恒 >5 或持续 <3 → `git revert 2c24885 a29e9b8 119af4d2`
- 线上 `AI_Score` 全空 → scan 仍可用（fallback 固定 1 Unit），单独修 `quant-research.yml`
- target 格式错 → 移除 `ENABLE_TARGET_FILE=1`（软关，无需 revert）
- AI 原因回填误开 → 确保 `ENABLE_AI_REASON_BACKFILL` 未设置（软关）

---

## 6. 关联产物（本周末产出，位于 /workspace）
- `WEEKEND_CHANGELOG.md`（本文件）
- `monday_check.sh`（8 项只读验证脚本）
- `archive/MONDAY_VERIFICATION_PLAN.md`（逐时点验证 + 回滚矩阵）
- `OPTIONS_WHEEL_DESIGN.md`（含 L2 实现草稿，wheel 模块待周一验证后启动）
- `preview/`（周一 UI 本地预览：截图 + mock `dashboard_data.json`）

---

## 8. 买入决策迁移（flag 门控）

> 来源：上一轮对话实施。目标是在**不激活**的前提下，把"买入决策"从 `review` 迁到 `scan`（`review` 只做成交价回填 + 复盘），并保留"默认关 → 周一/周二走旧路径"的安全网。本轮仅记录，不碰仓库。

### 8.1 目标与动机
- 原架构：买入决策在 **review** 阶段由 `portfolio_50000.py` 的 `process_buys` 执行（`review.yml` 跑完整 `run()`）。
- 理想架构：**scan 决定买不买**，review 只回填成交价 + 复盘。
- 规避点：防止 review 掌握"scan 之后到 review 之间"的美股开盘/收盘信息，构成潜在后见之明（look-ahead bias）。
  > 注：只读审计已确认原 `process_buys` **不读任何实时价/推荐后涨跌**，成交价固定用 `rec["Price"]`（scan 记录价），故严格意义上**不存在后见之明**；本次迁移属于架构直觉性收敛，非修复 bug。

### 8.2 实现方式（flag 门控，默认关闭）
- `portfolio_50000.py` 的 `run()` 新增两个可选分支（默认 `buy_only=False, no_buy=False`，**默认路径逐字节不变**）：
  - `--buy-only`：只跑 `process_buys`，跳过 `process_sells`（供 scan 调用）。
  - `--no-buy`：跳过 `process_buys`，其余照常（供 review 在 flag 开时调用）。
- 不碰 `run()` / `process_buys` / `process_sells` 核心逻辑，仅加参数分支 + flag 判断。

### 8.3 相关 commit
| SHA | Message | 影响文件 |
|---|---|---|
| `94804e9` | feat(portfolio): add --buy-only / --no-buy modes (flag-gated, default off) | `portfolio_50000.py`, `tests/test_buy_decision_flag.py` |
| `70dc941` | ci: add flag-gated scan buy decision (default off via repo var) | `.github/workflows/scan.yml`, `.github/workflows/review.yml` |
| `0839cfd` | fix(ci): conditionally commit ledger files when scan handles buy decision | `.github/workflows/scan.yml` |

### 8.4 flag 与 workflow 接线
- **flag**：`ENABLE_SCAN_BUY_DECISION`（repo variable，默认**不存在 = 关闭**）。
- `scan.yml`：env 注入 `${{ vars.ENABLE_SCAN_BUY_DECISION }}`；scan 跑完后加条件步骤 `if: env.ENABLE_SCAN_BUY_DECISION == '1'` 跑 `--buy-only`；提交块加 `if [ "${{ vars.ENABLE_SCAN_BUY_DECISION }}" = "1" ]` 条件 `git add` 账本文件（关闭时为空操作）。
- `review.yml`：分支 `if [ "${{ vars.ENABLE_SCAN_BUY_DECISION }}" = "1" ]; then --no-buy; else 原命令; fi`。
- **无任何硬编码 `"1"` 赋值**，仅 `== '1'` 比较操作数。

### 8.5 激活方式（周二验证后，人工手动）
> GitHub → 仓库 **Settings → Secrets and variables → Actions → Variables** → 新建：
> - Name: `ENABLE_SCAN_BUY_DECISION`
> - Value: `1`
> （激活前必须确认 `0839cfd` 的账本 `git add` 已随 scan 提交，否则 scan 的买入会在 review 的独立 runner 里被旧账本覆盖而丢失。）

### 8.6 关闭时行为（当前状态）
- repo variable 未设 → scan 的条件步骤 `if: env.ENABLE_SCAN_BUY_DECISION == '1'` 为 false → **跳过**；scan 走旧路径。
- review → `if [ "" = "1" ]` 为假 → 走 else 分支（原 `python portfolio_50000.py --data-dir .`）→ **行为不变**。
- 周一 21:00 scan、周二 06:23 review 全走旧路径。

### 8.7 回滚
- **软回滚（首选，零代码改动）**：删除 repo variable `ENABLE_SCAN_BUY_DECISION` → 所有条件分支立即回到旧路径，无需 revert 代码或重跑历史。
- **硬回滚（git revert，产生新提交，不改写历史）**：`git revert 0839cfd 70dc941 94804e9`（从新到旧），再 `git push origin main`。
