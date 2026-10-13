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
| 全量回归 | 387 passed（基线 382 + 新增 5） | ✅ **必须用 `python3.12`** |
| 文档入库 | 130 篇 `.md` → `docs/` | ✅ commit `dc6e06f` |
| 文档索引 | `DOCS_INDEX.md`（主题分组/状态/冲突） | ✅ 本日新增 |

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
- ⚠️ **全量测试必须用 `python3.12`**：`scan.py:2690` 含 f-string 反斜杠，**python3.11 无法解析**，用 3.11 会在 pytest 收集阶段直接失败（这不是你改坏了，是既有技术债）
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
| 4 | 🟠 统一「卡片 / 详情页 / review」三处止损数据源 | ANET 曾出现 197.69 / 209.36 / 210.24 三个值 | `ANET_STOPLOSS_TRIPLE.md`；根因是三套系统各算各的 |
| 5 | 🟠 为「推荐键匹配失败」加端到端断言 | 今日 bug 曾静默漏卖、无人察觉 | 已有告警打印，建议在 CI 上升为失败 |
| 6 | 🔴 **机械止损与 review 移动止损不一致（资金风险）** | 只读调查 `STOPLOSS_ROOT_CAUSE.md` | 机械止损按冻结的 197.69 判断，实际**放宽**了止损线（可能多亏 5–8%）；修法见下方展开 |
| 7 | 🟠 **`ENABLE_MARKET_INDICATORS` 已开，但面板仍未出现（修复中）** | 本次实测 dashboard-data run #2082 | 依赖已补齐，但又暴露**第二处根因：路径不匹配**，见下方展开 |

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
> **修复**：**C + D 组合**（明早 review 通过后做）
> - **C** = `portfolio_50000.py` 在 `mark_to_market()` 把 `Stop_Loss` 同步为 trade_history 的当前移动止损
>   （单文件、单一写入者、不新增跨模块耦合）
> - **D** = 拆掉并行的「第二套止损」：`_run_intraday_stop` 改读 trade_history，或直接下线 `dashboard-data.yml:93-97`
>   —— 让 review 成为唯一退出权威
> - 为什么不用 A（review 回写 positions.csv）：会引入 `positions.csv` 的第二个写入者，且 review 用 pandas 重写 CSV
>   可能与账本的 `POSITION_COLUMNS` 列序不一致，风险高于收益
>
> **时机**：**明早 07:00 后**
> （等 06:23 review 跑完并通过，避免与当晚生产复盘叠加变量）
>
> **注意**：C 会把机械止损线从 197.69 抬到 ~209，**原本不会触发的机械卖现在会触发**。
> 这是预期行为（197.69 早已失效），但属**真实的行为变更**，实施前需确认。

> #### P1 #7 展开 · 🟠 `ENABLE_MARKET_INDICATORS` 已开但面板仍未出现
>
> **状态**：修复中（2026-10-13）
>
> **根因（两处，缺一不可）**：
> 1. ✅ **已修 · 依赖缺失**：`fear-greed` / `cme-fedwatch` 未在 `requirements-production.txt` 声明。
>    修法 = 方案 i（加 2 行），commit **`60d55576`**。
> 2. 🔴 **未修 · 路径不匹配**：`dashboard/fetch_market_indicators.py:140` 默认写
>    `dashboard/data/market_indicators.json`，而 `dashboard_export.py:2460` 读的是
>    `data_dir / "market_indicators.json"`（= 仓库根，**少了 `dashboard/data/` 这一段**）。
>    读不到 → 返回哨兵 `_MARKET_INDICATORS_MISSING` → **不注入 `market_indicators` 键** → 前端整块隐藏。
>    - 设计文档本意就是 `dashboard/data/market_indicators.json`（`MARKET_INDICATORS_PANEL_DESIGN.md:147`）
>    - 输出侧 `dashboard_export.py:3001` 也写 `data_dir/"dashboard"/"data"/…`，**只有读取侧少了这段**
>    - 单测为何没抓到：`tests/test_market_indicators.py` 把文件放在 `tmp_path/market_indicators.json`，
>      与读取函数的**错误路径自洽**，所以永远测不出这个不匹配
>    - **最小修复（1 行）**：`dashboard_export.py:2460` →
>      `p = data_dir / "dashboard" / "data" / "market_indicators.json"`
>
> **影响**：不影响 scan（scan 不用这两个包）
>
> **验证**：dashboard-data run **#2082**（head `60d5557`）实测 ——
> - ✅ Install dependencies 成功（`cme-fedwatch-0.2.1` / `curl_cffi-0.16.3` 已装，耗时 +~17s）
> - ✅ Fetch market indicators 成功，日志 `[market_indicators] 已写入 dashboard/data/market_indicators.json（fear_greed=OK，fedwatch=OK）`
> - ✅ 文件已生成并入库（`dashboard/data/market_indicators.json`，3267 B）
> - ❌ **`dashboard_data.json` 仍无 `market_indicators` 键**（顶层仍 12 个 key）→ **面板仍未出现**
>
> → **修好路径后需再跑一次 dashboard-data 复验。**

### P2 — 功能推进（已决策待实施）

| # | 事项 | 依据 | 备注 |
|---|------|------|------|
| 8 | 盘中 Sparkline（方案 B：15 分钟粒度，画布放当前价下方） | `INTRADAY_SPARKLINE_DESIGN.md`，三项决策已定 | 实测 `app.js` 仍**无** `renderIntradaySpark` |
| 9 | 期权 Wheel 接线（CSP → CC） | `OPTIONS_WHEEL_DESIGN.md`（899 行） | flag 关、未接线 |
| 10 | 23 小时交易改造 | `23H_IMPLEMENTATION_DIFFS.md`（937 行草稿，最大） | `_us_session.py` **不存在**，尚未起步 |
| 11 | Model Fingerprint（识别中转站实际模型） | `MODEL_FINGERPRINT_METHOD.md` + `_IMPLEMENTATION.md` | 与 #1 的临时改动相关 |
| 12 | Scan 角色重定义（选 B：抽独立模块） | `SCAN_REDEFINITION_IMPLEMENTATION.md` | 设计已定，推进中 |

### P3 — 探索 / 可选

| # | 事项 | 依据 |
|---|------|------|
| 13 | Alpha101 因子引入 | `ALPHA101_FACTOR_RESEARCH.md` |
| 14 | 技术因子 OOS 加速实验落地 | `ACCELERATION_EXPERIMENT.md` |
| 15 | 事件日历 L2 | `ECON_CALENDAR_L2.md`（自述不实施） |
| 16 | 宏观板块 / Market Indicators 激活 | `MACRO_PANEL_ACTIVATION.md`、`MARKET_INDICATORS_PANEL_DESIGN.md`（当前阻塞见 P1 #7） |
| 17 | 80% 股票天花板取舍 | `POSITION_CEILING_EVAL.md` |
| 18 | Skill 框架 / Serenity-Skill | `SKILL_FRAMEWORK_DESIGN.md`、`SERENITY_SKILL_DESIGN.md` |
| 19 | 文档治理：把 130 篇中「已废弃」的归档 | `DOCS_INDEX.md` §15 |

> ⚠️ `cme-fedwatch` 依赖 `curl_cffi`（~13MB 二进制 wheel）—— 已确认 CI 能装
> （dashboard-data run #2082 实测），但会增加依赖安装时间约 10–15 秒（实测 +~17s）。

---

## 6. 交接速查

```bash
cd /tmp/us
python3.12 -m pytest tests/ -q          # 全量回归（387 passed；⚠️ 不能用 3.11）
git log --oneline -5                    # 最近提交
git ls-files | grep _temp               # 应为空（清理后）
grep -n "CLAWSOCKET_LIVE_MODEL" .github/workflows/review.yml   # 应为 claude-opus-5-5
grep -n "upstream_model" clawsocket_compat.py                  # 应无输出（debug 日志已删）
```

**当前 HEAD 附近**：`f03409b`(key 修复) → `021489a`(ANET 重置) → `dc6e06f`(docs 入库)；其上有自动刷新提交（`6636c98`、`cc8d60a` …）。

---

*本文件按只读整理生成，未触碰管线。有任何 flag 口径请以本文 §2.1 的**实测值**为准，而非历史文档中的描述。*
