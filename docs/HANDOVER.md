# HANDOVER — 美股量化跟踪臂 · 交接文档

> 生成时间：**2026-10-13（周二）11:55 北京时间**
> 全文所有时间均为**北京时间（UTC+8）**；GitHub Actions cron 为 UTC，换算见 §2。
> 配套索引：[`DOCS_INDEX.md`](./DOCS_INDEX.md)（130 篇遗留文档按主题分组 + 状态 + 冲突清单）
>
> ⚠️ 本文档为**只读整理**，未改动任何代码、未激活任何 flag。

---

## 1. 项目一句话概述

> **一个跑在 GitHub Actions 上的美股跟踪系统：Scan（盘中 AI 扫描推荐）→ Review（盘后复盘与止损裁决）→ Portfolio-50000（$50k 模拟账本记账/买入/卖出）→ Dashboard（静态页每 15 分钟刷新），辅以 Quant Research 因子实验室与 Options/News/Macro 等 flag 门控模块。**

数据/账本真相来源：`trade_history.csv`（推荐事件）· `portfolio_50000_positions.csv`（持仓）· `portfolio_50000_transactions.csv`（流水）。

---

## 2. 当前状态

### 2.1 Flag 现状（**逐条核对代码后**的实测值，非文档推断）

| Flag | 当前值 | 出处 | 说明 |
|------|--------|------|------|
| `ENABLE_TARGET_FILE` | ✅ **ON**（硬编码 `"1"`） | `scan.yml:46`、`dashboard-data.yml:58` | AI 目标持仓 `portfolio_50000_target.csv` 已在产出 |
| `ENABLE_AI_REASON_BACKFILL` | ✅ **ON**（硬编码 `"1"`） | `review.yml:52` | AI 理由回填已启用 |
| `ENABLE_MACRO_PANEL` | ✅ **ON**（repo variable = `1`，10-12 晚手动加） | `scan.yml:48,113` | scan 落盘 `macro_data.json` → 宏观板块**应渲染**；前端缺该文件才显示「尚未开启」 |
| `ENABLE_SCAN_BUY_DECISION` | ❓ **未知** | `scan.yml:47,55,123`、`review.yml:61` | `vars.` 值本地不可见，需查 GitHub Settings |
| `ENABLE_MARKET_INDICATORS` | ❓ **未知** | `dashboard-data.yml:62,104` | `vars.` 值本地不可见，需查 GitHub Settings |
| `ENABLE_OPTIONS_WHEEL` | ⭕ **OFF**（代码默认关） | `option_wheel.py:9,37` | 代码默认值本地可判定 |

**结论：2 个硬编码 flag 常开（target / reason-backfill）；`ENABLE_MACRO_PANEL` 已 ON；`ENABLE_OPTIONS_WHEEL` 代码默认关；其余 2 个以 `vars.` 驱动的值本地无法判定。**

> ⚠️ **repo variable 的实际值以 GitHub Settings 为准；本地代码只能看到 `${{ vars.X }}` 引用，无法判断是否已设。**
> 因此：上表中`硬编码`与`代码默认`两类可由本地代码判定，`vars.` 类必须去 **GitHub → Settings → Secrets and variables → Actions → Variables** 复核，**切勿据本地代码断定其为 OFF**（本条由 2026-10-13 修正：`ENABLE_MACRO_PANEL` 曾被误判为 OFF）。

### 2.2 排程现状

| 任务 | Workflow | 触发方式 | 北京时间 |
|------|----------|---------|---------|
| Review 复盘 | `review.yml` | GitHub cron `23 22 * * 1-5` | 06:23（周二~周六） |
| Dashboard 刷新 | `dashboard-data.yml` | GitHub cron `*/15 * * * 1-5` | 工作日每 15 分钟 |
| Scan 扫描 | `scan.yml` | ⚠️ **仅 `workflow_dispatch`，无 cron** | 依赖外部触发（cron-job.org）或手动 Run |

> 🔴 **重要修正**：多份历史 checklist 写着「每晚 21:00 scan 自动跑」，但实测 `scan.yml` 的 `on:` **只有 `workflow_dispatch:`**（第 4 行），没有任何 cron。GitHub 侧**不会自动排程**扫描；21:00 那次依赖 cron-job.org 外部调用或人工 dispatch。请勿假设它会自动跑。

### 2.3 今日（10-13）已完成

| 项 | 内容 | 状态 |
|----|------|------|
| STOPLOSS key bug 修复 | `rec_id_of` 日期归一化（`portfolio_50000.py`）+ 漏卖告警 | ✅ commit `f03409b` |
| ANET 状态重置 | `Stop_Loss_Hit`→`Active`，清 Exit_Date/Exit_Price，`STOP_TRIGGERED`→`CLEAR` | ✅ commit `021489a`（仅改 ANET 一行） |
| 全量回归 | `PYTHONUTF8=1 python3.12 -m pytest tests/ -q`（数量随用例增长；2026-10-13 实测 **499 passed**；⚠️ Windows 本机需 `PYTHONUTF8=1`，否则子进程用例 GBK 解码失败） | ✅ **必须用 `python3.12`** |
| 文档入库 | 130 篇 `.md` → `docs/` | ✅ commit `dc6e06f` |
| 文档索引 | `DOCS_INDEX.md`（主题分组/状态/冲突） | ✅ 本日新增 |
| 模型统一 | 所有 workflow + 模块默认模型改为 `claude-fable-5-1`（共 11 处，含 4 个 workflow 的 `CLAWSOCKET_LIVE_MODEL`） | ✅ commit `3ed5a4bb` |
| 模型展示 | 网页显示运行时模型（`MODEL_DISPLAY_TASK.md`） | ✅ 已实施（`3edd7bb4` + `cf52915f`），待 21:00 scan 复验 |

**还没完成的验证**：今夜 21:00 scan（若外部触发到达）；明早 06:23 review 对 ANET 的重新判定。

---

## 3. 下一步行动清单（含时间）

### 今晚 · 周二 2026-10-13

| 时间 | 动作 | 通过标准 | 异常处置 |
|------|------|---------|---------|
| **21:00** | 看 Actions 是否有 `美股盘中扫描` run | 出现 1 次 run | **没跑** → 手动 Run workflow（因为本就无 cron，属预期，不必惊慌） |
| **21:05** | scan 是否成功 | 步骤全绿、无 KeyError | 失败 → 截图日志，`git status` 确认无脏文件 |
| **21:30** | 打开站点核对渲染 | 组合 4 只 ✅ / AI 目标卡片 ✅ / 交易观测面板 ✅ / **宏观板块应显示**（`ENABLE_MACRO_PANEL` 已 ON） | 宏观显示「尚未开启」→ 说明 21:00 scan 没跑或 `macro_data.json` 未生成，**不是** flag 关 |

### 明早 · 周三 2026-10-14

| 时间 | 动作 | 通过标准 | 异常处置 |
|------|------|---------|---------|
| **06:23** | Review 定时触发 | Actions 出现 1 次 `美股盘后复盘` | 0 次/报错 → 保留日志，**不要手动补跑**（会重复记账本） |
| **06:23** | 🎯 **验证 ANET 修复效果** | ANET 被按当日实际价重新判定；若触发止损 → 账本**应真正卖出**（漏卖 bug 已修） | 若 ANET 终态却未被卖出 → 检查是否又出现键/状态错配 |
| **07:00** | 跑 `monday_check.sh` | review run 数与 06:23 肉眼计数一致 | 不一致 → 截图留证，不补跑 |
| **全天** | 观察 4 只持仓（ADSK/ANET/ISRG/KR） | 除 ANET 按 review 裁决外，其余 3 只**不应**被意外卖出（均为 Active） | 出现意外卖出 → 立即冻结、回滚 ledger |

### 🧹 待清理（**已实测确认仍然存在**，非推断）

| # | 待办 | 位置 | 备注 |
|---|------|------|------|
| 1 | 🔴 回滚模型：把 `gpt-6-astra` 改回 `claude-opus-5-5` | `.github/workflows/review.yml:51` | 当时为测试临时改，commit `89eedaa` 已注明 temporarily |
| 2 | 🟠 删除两个临时 workflow | `.github/workflows/_temp-acceleration.yml`、`_temp-test-datasources.yml` | 结果看完后删；删前确认已下载 acceleration artifact |
| 3 | 🟠 删除临时实验脚本 | `_temp_experiment/`（4 个 .py） | 同上 |
| 4 | 🟡 删除/保留 debug 日志 | `clawsocket_compat.py:280`（`[ClawSocket] upstream_model=`） | 与 #1 配套；回滚模型后可一并去掉 |

清理统一走：`git rm -r` → `git commit` → `git fetch` → `git rebase origin/main` → `git push`（**不 amend / 不 force**）。

---

## 4. 铁律（⛔ 不要做的事）

### 4.1 不能碰的文件（观测期内）

| 文件 / 模块 | 原因 |
|------------|------|
| `review.py` / `review.yml` | 每日 06:23 生产复盘，改动风险最高（**受影响的例外**：仅允许 §3 清理 #1 那一行 model env） |
| `scan.py` / `scan.yml` | 每晚生产扫描；且含未修的 PEP701 技术债 |
| macro 相关（`macro_data.json` / `write_macro_data` / 宏观渲染） | macro 首次跑的磨合期，先读日志不动源码 |
| `trade_history.csv` / `portfolio_50000_positions.csv` / `portfolio_50000_transactions.csv` | **账本真相来源**，禁止手改。唯一例外是今日已授权的 ANET 单行重置 |
| `dashboard-data.yml` 的 concurrency / 提交逻辑 | 曾出并发删除 Bug，改动易复发 |

### 4.2 不能改的 flag

- ❌ **不要把 `ENABLE_TARGET_FILE` / `ENABLE_AI_REASON_BACKFILL` 关掉**（硬编码常开，下游 dashboard 依赖）
- ⚠️ **`ENABLE_MACRO_PANEL` 已 ON**（repo variable = 1）——观测期**保持原状不要动**；改动会引入「macro 首次跑」之外的变量
- ❌ **观测期不要打开 `ENABLE_SCAN_BUY_DECISION`**（会把买入决策从账本切给 scan，链路质变）。当前值未知，行动前先查 GitHub Settings
- ❌ **`ENABLE_MARKET_INDICATORS` 未确认前不要打开**（F&G / FedWatch 数据源待确证）
- ❌ **不要打开 `ENABLE_OPTIONS_WHEEL`**（未验收）
- ⚠️ 发现 flag 被误设时，按 `WEEKEND_CHANGELOG.md` §3 回滚矩阵**删 repo variable**，不改代码

### 4.3 流程铁律

- ⛔ **永不 `git commit --amend` / `git push --force`**（含 `--force-with-lease`）
- ⛔ **不要手动补跑 review**（同 group 串行，但重复跑会重复记账本流水）
- ⚠️ **全量测试必须用 `python3.12`**：`scan.py` 风控 prompt 模板里的 `{'\n'.join(position_lines)}`（f-string 表达式内含反斜杠）在 3.11 无法解析，用 3.11 会在 pytest 收集阶段直接失败（这不是你改坏了，是既有技术债）
- ⚠️ **不要回退 `rec_id_of` 的日期归一化**（今日修复；回退会让所有持仓重新变成「漏卖」）
- ⚠️ 每次 push 前：`git fetch origin` → `git rebase origin/main` → `git push`（远端常被自动 `refresh market data` 提交推进）

---

## 5. 未来 Backlog（**仅记录，本轮不改代码**）

### P1 — 正确性 / 风险（建议优先）

| # | 事项 | 依据 | 备注 |
|---|------|------|------|
| 1 | 🔴 回滚 `review.yml` model → `claude-opus-5-5` | 临时测试改动未回滚，影响每日复盘质量 | 配套删 debug 日志 |
| 2 | 🔴 修 `scan.py` PEP701（f-string 反斜杠） | 导致 3.11 不可用、工具链被迫锁 3.12 | `PEP701_TECHDEBT_REPORT.md` 确认但未修 |
| 3 | 🟠 清理 `_temp-` 遗留（2 workflow + 4 脚本） | 临时资产混在生产库，有误触发风险 | 清理前确认结果已复核 |
| 4 | 🟠 统一「卡片 / 详情页 / review」三处止损数据源 | ANET 曾出现 197.69 / 209.36 / 210.24 三个值 | `archive/ANET_STOPLOSS_TRIPLE.md`；根因是三套系统各算各的 |
| 5 | 🟠 为「推荐键匹配失败」加端到端断言 | 今日 bug 曾静默漏卖、无人察觉 | 已有告警打印，建议在 CI 上升为失败 |
| 6 | 🟡 **机械止损与 review 移动止损不一致（资金风险）— 修复已实现，待激活** | `STOPLOSS_ROOT_CAUSE.md` + 实测 | 方案 C 已落地，门控在 `ENABLE_STOP_LOSS_SYNC`（**默认关闭**）；激活方式与一项新发现见下方展开 |
| 7 | ✅ **`ENABLE_MARKET_INDICATORS` 已开但面板不出现（已修复）** | 实测 run #2082 → 复验 #2084 | 两处根因：① 依赖缺失 ② 读取路径不匹配；均已修并有回归测试 |
| 8 | 🔴 **`dec()` 不解析 `$` 前缀 → 盘中机械止损从未真正生效** | 2026-10-13 实测（P1 #6 调查中发现） | 4 只持仓的 `Stop_Loss` 全是 `$` 前缀 → `dec()` 返回 None → `_run_intraday_stop` 全部跳过；详见下方展开 |

> #### P1 #6 展开 · 🔴 机械止损与 review 移动止损不一致（资金风险）
>
> **问题**：机械止损按 `portfolio_50000_positions.csv` 里**冻结的初始止损（197.69）**判断，
> 而 review 按**移动止损（210.24）**判断。两者不一致，**机械止损实际放宽了止损线（可能多亏 5–8%）**。
>
> - 机械止损取值：`portfolio_50000.py:687`（`_run_intraday_stop`），由 `dashboard-data.yml:93-97` 每 15 分钟驱动
> - 该值**全仓库唯一写入点**是建仓时的 `portfolio_50000.py:555`，持仓期间**永不更新**
>   （`mark_to_market()` `:566-603` 只改价格/浮盈字段，不碰 `Stop_Loss`）
> - review 的移动止损其实**有落盘**，但落在 `trade_history.csv`（`review.py:1426-1448`，调用点 `:1878-1882`）——
>   **账本机械止损不读它**
> - 触发时 review 还会跳过回写（`review.py:1875-1876` `continue`），所以日志的 210.24 与落盘的 209.36 本身也会差一拍
> - ⚠️ 更根本的矛盾：`portfolio_50000.py:5-11` docstring 明写「卖出完全沿用 Review 终态……**本模块不实现第二套止损**」，
>   而 `_run_intraday_stop` 就是那"第二套"，且挂在一个永不更新的值上
>
> **修复**：**C + D 组合**
> - **C** = `portfolio_50000.py` 在 `mark_to_market()` 把 `Stop_Loss` 同步为 trade_history 的当前移动止损
>   （单文件、单一写入者、不新增跨模块耦合）→ ✅ **已实现**
> - **D** = 拆掉并行的「第二套止损」：`_run_intraday_stop` 改读 trade_history，或直接下线 `dashboard-data.yml:93-97`
>   —— 让 review 成为唯一退出权威 → ⏳ **未做**
> - 为什么不用 A（review 回写 positions.csv）：会引入 `positions.csv` 的第二个写入者，且 review 用 pandas 重写 CSV
>   可能与账本的 `POSITION_COLUMNS` 列序不一致，风险高于收益
>
> **实现状态（2026-10-13）**：方案 C ✅ 已落地，commit **`0b55de72`**，新增 34 个测试。
> - 门控 flag：**`ENABLE_STOP_LOSS_SYNC`**，`== "1"` 才生效；**默认不设 = 关闭**。
> - 代码：`portfolio_50000.py` 新增 `stop_sync_enabled()` / `_sync_stop_loss_from_recs()`；
>   `mark_to_market(positions, prices, today, recs=None)` 增加可选 `recs`；
>   `run()` 的两个调用点（`--price-only` 与完整 run）均已接线。
> - **关闭时逐字节一致（硬证据）**：用 `git show HEAD:portfolio_50000.py` 取出改动**前**的模块，
>   在同一份真实 `positions.csv` 上跑 `--price-only --offline`，与改动后（flag 不设）的输出
>   **SHA256 完全相同**（`87F0C688…993C`）。
> - **激活方式**（明早 06:23 review 通过后）：
>   `gh variable set ENABLE_STOP_LOSS_SYNC 1`（或 GitHub → Settings → Secrets and variables → Actions → Variables）
> - **关闭时**：`_sync_stop_loss_from_recs` 整体不被调用；`--price-only` 连 `trade_history` 都不读。
>
> 🔴 **实测新发现（比原报告更严重，建议单独立项）**：
> `dec()`（`portfolio_50000.py:94`）**只剥逗号、不剥 `$`**，故 `dec("$197.69") is None`；
> 而 `_run_intraday_stop:687-689` 是 `stop = dec(...)` → `if stop is None: continue`。
> **当前 4 只持仓的 `Stop_Loss` 全是 `$` 前缀**（`$214.76` / `$197.69` / `$382.38` / `$56.31`）
> → **盘中机械止损对这 4 只从未生效过**（不是"用了陈旧值"，而是被整条跳过）。
> - 方案 C 的同步恰好能修好它：同步写的是**归一化后的裸数字**（`228.29` 而非 `$214.76`），
>   因此 flag 一开，4 只的止损线立即变为可解析值，机械止损随之真正生效。
> - 副作用（**可见但轻微**）：卡片 `Stop_Loss` 显示从 `$214.76` 变成 `228.29`（少了 `$`）。
> - 若只想保留 `$` 格式，则 `dec()` 也必须同步支持 `$` —— 那会动到 `dec()` 的全部调用点，**不建议本次做**。
>
> **注意**：flag 一开，机械止损线会从 `197.69` 抬到 `~209`（ANET），**原本不触发的机械卖现在会触发**。
> 这是预期行为（那 4 条线此前完全失效），但属**真实的行为变更**，激活前需确认。
> 另建议同时评估 **D**（下线并行的第二套止损，让 review 成为唯一退出权威）。

> #### P1 #7 展开 · ✅ `ENABLE_MARKET_INDICATORS` 已开但面板不出现（**已修复**）
>
> **状态**：✅ **已修复（2026-10-13）**
>
> **根因（两处，缺一不可）**：
> 1. ✅ **依赖缺失**：`fear-greed` / `cme-fedwatch` 未在 `requirements-production.txt` 声明。
>    修法 = 方案 i（加 2 行），commit **`60d55576`**。
> 2. ✅ **路径不匹配**：`dashboard/fetch_market_indicators.py:140` 默认写
>    `dashboard/data/market_indicators.json`，而 `dashboard_export.py:2460` 读的是
>    `data_dir / "market_indicators.json"`（= 仓库根，**少了 `dashboard/data/` 这一段**）。
>    读不到 → 返回哨兵 `_MARKET_INDICATORS_MISSING` → **不注入 `market_indicators` 键** → 前端整块隐藏。
>    - 设计文档本意就是 `dashboard/data/market_indicators.json`（`archive/MARKET_INDICATORS_PANEL_DESIGN.md:147`）
>    - 输出侧 `dashboard_export.py:3001` 也写 `data_dir/"dashboard"/"data"/…`，**只有读取侧少了这段**
>    - **修复（1 行 + 1 回归测试）**：commit **`27d004e6`**
>      - `dashboard_export.py:2460` → `p = data_dir / "dashboard" / "data" / "market_indicators.json"`
>      - 新增 `tests/test_market_indicators.py::test_read_path_must_be_dashboard_data_regression`：
>        把文件放在**真实嵌套位置**，并断言根目录那份读不到。**修复前该测试确实失败**（已验证），
>        修复后通过 → 未来谁把路径改回去，测试立刻红。
>      - 顺带修正原有 `test_flag_off_guard_and_export_no_key`：它原本把文件写在
>        `tmp_path/market_indicators.json`，**与错误路径自洽**，所以永远抓不到这个 bug。
>
> **影响**：不影响 scan（scan 不用这两个包）
>
> **验证**：dashboard-data run **#2084**（head `27d004e6`，13:27:30 → 13:29:57 北京，conclusion=success）
> - ✅ `Install dependencies` 成功；`Fetch market indicators` 成功
>   （日志 `[market_indicators] 已写入 dashboard/data/market_indicators.json（fear_greed=OK，fedwatch=OK）`）
> - ✅ `Run dashboard_export.py` 成功
> - ✅ `dashboard/data/market_indicators.json` 已入库（3267 B，`generated_at=2026-10-13T05:29:11Z`）
> - ✅ `dashboard_data.json` **已含 `market_indicators` 键**（raw 与 pages 两份均已确认）：
>   `fear_greed.score=45.4 / rating=neutral`，`fedwatch.next_meeting=2026-10-28`
> - ✅ 前端「📊 市场情绪指标」面板**已渲染**（payload 就位；渲染逻辑由
>   `test_frontend_render_with_data` 覆盖）
>
> ⚠️ **附带修复（同日）**：`requirements-production.txt` 加入这两个包后，
> `tests/test_market_indicators.py` 有两个**环境脆弱用例**会失败 —— 它们靠"包恰好没装"来构造失败分支：
> - `test_fg_fails_fw_ok`（假设 `fear_greed` 不可导入）
> - `test_both_sources_fail_no_file`（假设两包都不可导入）
>
> ✅ **已修**：新增 `_block_imports()` helper，用 `monkeypatch` 覆盖 `builtins.__import__`
> 强制抛 `ImportError`（只拦白名单包，其余一律委托真实实现），两个用例已 hermetic。
> **全量回归：`PYTHONUTF8=1 python3.12 -m pytest tests/ -q`，0 failed**（数量随用例增长；2026-10-13 实测 **499 passed**；Windows 本机需 `PYTHONUTF8=1`）。
>
> 注：CI 无 pytest runner（无任何 test workflow），此类环境脆弱问题只影响本地全量跑。

> #### P1 #8 展开 · 🔴 `dec()` 不解析 `$` 前缀 → 盘中机械止损从未真正生效
>
> **发现于**：P1 #6 的实现验证过程中（2026-10-13，跑 `ENABLE_STOP_LOSS_SYNC` 真实数据演练时暴露）。
>
> **根因**：`dec()`（`portfolio_50000.py:94`）只做 `Decimal(str(v).replace(",", "").strip())`
> —— **剥逗号、剥空格，但不剥 `$`**，因此 `dec("$197.69") is None`。
> 而 `_run_intraday_stop:687-689` 是 `stop = dec(p.get("Stop_Loss"))`，
> 紧接着 `if stop is None or stop <= 0: continue` —— **直接跳过该持仓**。
> **当前 4 只持仓的 `Stop_Loss` 全是 `$` 前缀**（实测）：
> `ADSK '$214.76'` / `ANET '$197.69'` / `ISRG '$382.38'` / `KR '$56.31'` → `dec()` 全为 None
> → **盘中机械止损对这 4 只从未执行过任何检查**。
>
> ⚠️ 这比 `STOPLOSS_ROOT_CAUSE.md` 的原判断更严重：原报告说 197.69「因价格距离远而惰性失效」，
> 实际原因是**值根本无法解析**，与价格无关 —— 任何价格都不会触发。
>
> **修复路径（已就绪，随 P1 #6 的 flag 一起生效）**：
> `ENABLE_STOP_LOSS_SYNC` 的同步逻辑写的是**归一化后的裸数字**（`raw_stop.replace("$", "")`），
> 所以 flag 一开，这 4 条止损线立即变成可解析值，机械止损才真正开始工作。实测同步结果：
> `ADSK 228.29` / `ANET 209.36` / `ISRG 411.24` / `KR 59.79`（`dec()` 全部可解析 ✅）。
>
> **附带影响（需知悉）**：卡片 `Stop_Loss` 显示会从 `"$214.76"` 变成 `"228.29"`（少一个 `$`）。
> 若要坚持保留 `$` 格式，则必须让 `dec()` 也支持 `$` —— 那会波及 `dec()` 的**全部调用点**
> （价格 / 股数 / 金额解析都走它），风险面大，**建议单独立项、独立验证**。
>
> **时机**：已随 P1 #6 的 flag 一起待激活；若决定保留 `$`，需先做 `dec()` 改造再评估。

### P2 — 功能推进（已决策待实施）

| # | 事项 | 依据 | 备注 |
|---|------|------|------|
| 9 | 盘中 Sparkline（方案 B：15 分钟粒度，画布放当前价下方） | `archive/INTRADAY_SPARKLINE_DESIGN.md`，三项决策已定 | 实测 `app.js` 仍**无** `renderIntradaySpark` |
| 10 | 期权 Wheel 接线（CSP → CC） | `OPTIONS_WHEEL_DESIGN.md`（899 行） | flag 关、未接线 |
| 11 | 23 小时交易改造 | `archive/23H_IMPLEMENTATION_DIFFS.md`（937 行草稿，最大） | `_us_session.py` **不存在**，尚未起步 |
| 12 | Model Fingerprint（识别中转站实际模型） | `archive/MODEL_FINGERPRINT_METHOD.md` + `archive/MODEL_FINGERPRINT_IMPLEMENTATION.md` | 与 #1 的临时改动相关 |
| 13 | Scan 角色重定义（选 B：抽独立模块） | `SCAN_REDEFINITION_IMPLEMENTATION.md` | 设计已定，推进中 |
| 14 | 🟡 **git 全局 `curloptResolve` pin 不稳定** | 2026-10-13 实测 | 见下方展开 |
| 15 | 🟠 **网页显示运行时模型**（MODEL_DISPLAY_TASK.md） | 见下方展开 | 让用户看出中转站是否偷换模型 |

> #### P2 #14 展开 · 🟡 git 全局 `curloptResolve` pin 不稳定
>
> - **现象**：`git fetch` / `git push` **偶发失败**（`exit 128`，连接超时 / `Recv failure: Connection was reset`）。
>   重试即可通过 —— 实测 fetch 连失 2 次后第 3 次成功；push 失败 1 次后重试成功。
> - **当前 pin**：`github.com:443:140.82.112.3`，写在 `~/.gitconfig` 的 `http.curloptResolve`。
>   **起因**：本机 DNS 把 `github.com` 解析到亚洲节点 `20.205.243.166`，该 IP 完全不可达；
>   其它 GitHub 域名（api / raw / codeload / lfs）均正常。
> - **修法**：换一个可达的美区 IP（`140.82.113.3` / `140.82.114.3` / `140.82.121.3` 实测均可达），
>   或改用 hosts 条目把 `github.com` 固定到可用 IP（需管理员）。
> - **时机**：不急，重试能过；但今天已经在 P1 #7 的收尾 push 上真实卡过一次。

> #### P2 #15 展开 · 🟠 网页显示运行时模型
>
> - **状态**：🔴 **待实施**（完整任务规格见 [`MODEL_DISPLAY_TASK.md`](MODEL_DISPLAY_TASK.md)，可直接交给新会话执行）
> - **目的**：让用户能一眼看出**中转站是否偷换了模型**。
> - **触发原因**：2026-10-13 实测已出现「请求模型 ≠ 实际模型」——
>   scan 日志里 `请求引擎: claude-opus-5-5`，紧接着
>   `⚠️ [ClawSocket] … 路由失败；尝试运行时备用模型 claude-fable-5-1`；
>   而同一次运行的另一行却是 `upstream_model=claude-opus-5-5`。
>   **即模型到底是哪个只存在于 stdout 日志，网页上完全看不到**，
>   而模型质量直接影响 scan 选股与 review 复盘质量。
> - **做法**：`clawsocket_compat.py` 加模块级累积器（`set_context` / `record_model_usage` /
>   `write_model_usage`）→ 落盘 `dashboard/data/model_usage.json` →
>   `dashboard_export.py` 注入 → `app.js` 的 runtime 条在 `SCAN ✓` 后追加模型小字。
> - **相关**：P2 #12（Model Fingerprint）是更深一层的同类问题；本项是它的"轻量可视版"。

### P3 — 探索 / 可选

| # | 事项 | 依据 |
|---|------|------|
| 16 | Alpha101 因子引入 | `ALPHA101_FACTOR_RESEARCH.md` |
| 17 | 技术因子 OOS 加速实验落地 | `archive/ACCELERATION_EXPERIMENT.md` |
| 18 | 事件日历 L2 | `archive/ECON_CALENDAR_L2.md`（自述不实施） |
| 19 | 宏观板块 / Market Indicators 激活 | 已完成，见 P1 #7 |
| 20 | 80% 股票天花板取舍 | `archive/POSITION_CEILING_EVAL.md` |
| 21 | Skill 框架 / Serenity-Skill | `archive/SKILL_FRAMEWORK_DESIGN.md`、`archive/SERENITY_SKILL_DESIGN.md` |
| 22 | 文档治理：把 130 篇中「已废弃」的归档 | `DOCS_INDEX.md` §15 |

> ⚠️ `cme-fedwatch` 依赖 `curl_cffi`（~13MB 二进制 wheel）—— 已确认 CI 能装
> （dashboard-data run #2082 实测），但会增加依赖安装时间约 10–15 秒（实测 +~17s）。

---

## 6. 交接速查

```bash
cd /tmp/us
PYTHONUTF8=1 python3.12 -m pytest tests/ -q   # 全量回归（数量随用例增长；2026-10-13 实测 499 passed；⚠️ 不能用 3.11；Windows 必须 PYTHONUTF8=1）
git log --oneline -5                    # 最近提交
git ls-files | grep _temp               # 现状 6 条（_temp_experiment/ ×4 + 2 个 _temp-*.yml），尚未清理
grep -n "CLAWSOCKET_LIVE_MODEL" .github/workflows/review.yml   # 应为 claude-fable-5-1（已全库统一）
grep -n "upstream_model" clawsocket_compat.py                  # 应有输出（clawsocket_compat.py:345，供 dashboard 展示模型名，非 debug 残留）
```

**当前 HEAD 附近**：`f03409b`(key 修复) → `021489a`(ANET 重置) → `dc6e06f`(docs 入库)；其上有自动刷新提交（`6636c98`、`cc8d60a` …）。

---

*本文件按只读整理生成，未触碰管线。有任何 flag 口径请以本文 §2.1 的**实测值**为准，而非历史文档中的描述。*
