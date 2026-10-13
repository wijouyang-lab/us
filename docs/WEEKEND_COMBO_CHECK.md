# 周末组合体检报告（第二轮 · 只读静态分析）

> **执行方式**：纯只读。仅用 `git` / `grep` / 文件读取做静态分析，**未运行任何 `.py`**、未改代码、未 push/rebase、未碰监控、未调 AI。
> **范围**：17 个周末 commit（`683b45b`→`623e06f`）之间的**组合交叉风险**，不重复单项单测结论。
> **生成时间**：2026-10-10 23:58 (GMT+8)

---

## 0. 数据流总览（检查 1 底色）

```
cron-job.org / workflow_dispatch
   ↓
scan.yml (us-stock-scan 组, cancel=false)
   ├─ scan.py                严筛 MIN_SCORE=80 → 候选 0-3 只
   │                         浮动手数(持仓~4)+候选≤3 → AI 输入 ≤7
   │                         写 pending CSV / ai_text_cache / ai_snapshot
   │                         [ENABLE_TARGET_FILE=1] 写 portfolio_50000_target.csv
   ├─ quant_factor_price.py  价格历史 upsert
   ├─ upload-artifact        安全网（防 push 失败丢数据）
   ├─ git add + rebase+push  ← 提交 pending/snapshot/target
   ↓ needs: scan
news-fetch.yml (news-fetch 组)        → 写 news_data.json → push
quant-research.yml (quant-research 组)→ 写研究产物(14文件) → push
   ↓ 定时（与 scan 无关）
dashboard-data.yml (dashboard-data-refresh 组, */15 * * * 1-5)
   ├─ --price-only           写 portfolio_50000_positions.csv（仅价格）
   ├─ --intraday-stop        09:30-16:00 ET 内写 positions+transactions
   └─ dashboard_export.py    读 target.csv[flag] → 注入 portfolio.target
   ↓
前端 app.js / index.html
   ↓ 定时（与 scan 无关）
review.yml (us-stock-review 组, 23 22 * * 1-5 UTC)
   ├─ [ENABLE_AI_REASON_BACKFILL=1] backfill_pending_reasons（调 AI）
   └─ portfolio_50000.py 全量 run → 写 positions+transactions+history+meta → push
```

### 检查 1 · 五个子问题

| # | 问题 | 结论 | 证据 |
|---|------|------|------|
| 1 | scan 写 target 的 commit guard 覆盖了吗？ | ✅ 已覆盖 | `scan.yml:99-101` `if [ -f portfolio_50000_target.csv ]; then git add ...`；`scan.py:3957` `if ENABLE_TARGET_FILE=="1": write_portfolio_target_csv(...)`；`scan.yml:46` 设该 flag |
| 2 | 浮动手数(3-5) 与 target 文件关系——target 写几只？ | target 写 **持仓数+候选数**（上限 ~7），与"浮动 3-5"是**不同口径**（后者是 process_buys 的当前持仓闸门） | `portfolio_target.py:147-181` 写 HOLD(持仓∩推荐)+BUY(候选)+SELL(持仓∉推荐)；`portfolio_50000.py:495-501` 闸门 3 限制当前持仓 |
| 3 | quant-research push retry 与 news-fetch push 会撞吗？ | ⚠️ 会"撞"（同时 push 同 main）但**不丢数据**（写不相交文件），仅多几次重试噪声 | `scan.yml:160-172` 二者并列 `needs:scan` 并行；`news-fetch.yml:57-79` / `quant-research.yml:82-98` 各自 `reset --soft FETCH_HEAD` 重试 |
| 4 | --price-only 与 review run() 并发？ | 🔴 **高危**：二者独立并发组，都写 `positions.csv`（见 H1） | `dashboard-data.yml:86` + `portfolio_50000.py:773` 仍写 positions；`review.yml:58` 全量写 positions+transactions |
| 5 | AI 回填 flag 与 dashboard-data 并发？ | ⚠️ 回填在 review 内执行，review 本就与 dashboard-data 抢同一账本；flag 不新增文件争用，但引入 AI 成本与"回填文本是否被随后 run 覆盖"风险（见 M4） | `review.yml:52` 设 flag；`review.py:3820-3824` 调用 backfill；`review.yml:58` 随后跑全量 portfolio |

---

## 1. 所有 flag 状态（检查 2）

```
grep -rn "ENABLE_" --include="*.yml" --include="*.yaml" --include="*.py" .
```

| Flag | 默认值 | 设置位置 | 设置值 | 对应功能 | 误设？ |
|------|--------|----------|--------|----------|--------|
| `ENABLE_TARGET_FILE` | 关闭（代码 `== "1"` 才生效） | `scan.yml:46` | `"1"` | scan 落盘 `portfolio_50000_target.csv` | ✅ 预期 |
| `ENABLE_TARGET_FILE` | 同上 | `dashboard-data.yml:58` | `"1"` | dashboard_export **读** target 并注入 `portfolio.target` | ✅ 预期（读侧须与写侧一致） |
| `ENABLE_AI_REASON_BACKFILL` | 关闭 | `review.yml:52` | `"1"` | review 调 AI 回填 `Pending_Reason` | ✅ 设计预期（但**周一 review 会真实调 AI**，见 M4） |
| `ENABLE_OPTIONS_WHEEL` | 关闭 | 任何 yml **均未设置** | 不设 | wheel L2 模块（C 任务，未接线、无调用点） | ✅ 正确（默认关闭） |
| `DASHBOARD_AI_ENABLED` | — | `dashboard-data.yml:52` | `"false"` | 审计标记（声明 dashboard 不调 AI） | ✅ 正确 |

**结论：无 flag 被误设。** 唯一需运营确认的是 `ENABLE_AI_REASON_BACKFILL="1"` 已激活——它会在周一（实为周二北京 06:23）review 真实消耗 AI 配额回填 `Pending_Reason`。

> 注：`ENABLE_TARGET_FILE` 在**两个** workflow 出现属正确分工（scan 写、dashboard 读），非重复误设。

---

## 2. 新增字段向后兼容（检查 3）

| 字段 | 写入方 | 旧数据缺字段时后端 | 前端缺字段时 |
|------|--------|-------------------|--------------|
| `Cooldown_Until`（positions.csv） | `process_sells:438` / intraday `:730` | `write_csv_rows:238` 用 `r.get(c,"")` 写空；`_load_cooldowns:135` 用 `p.get("Cooldown_Until","")` 读 → 旧行自动跳过，**不崩** | 前端不读该字段 |
| `Pending_Reason`（transactions.csv） | intraday `:720` | `TRANSACTION_COLUMNS:66` 新列；`write_csv_rows` 用 `.get` 写空，**不崩** | `renderStopped`(app.js:629) 读 `action/reason/realized_pnl/amount`，**不读** `Pending_Reason` → 忽略，不崩 |
| `open_pct`（dashboard_data.json） | `dashboard_export.py:2562-2564` | 防御 `else 0.0`，`Stock_Value/Total_Equity` 缺失→0.0，**不崩** | 前端读 `pf.open_pct`，缺失→`num()` 兜底 0 |
| `market_relevant`（news_data.json） | `fetch_news.py:365,478` | 旧新闻缺字段时前端 `isMarketRelevant`(app.js:969) `!x \|\| x.market_relevant !== false` → 缺字段被 **KEEP**（兼容旧数据全显示）；新数据 `false` 才过滤，**不崩** | 同上 |
| `target`（dashboard_data.json） | `dashboard_export.py:2543` 读 target.csv 注入 | 文件缺失/解析失败 → `_read_portfolio_target:2424-2430` 返回 `None`；flag 关 → `target=None` | `app.js:486-487` `if (!target \|\| !target.length)` 静默隐藏，**不崩** |

**结论：5 个新增字段全部向后兼容，旧数据 / 字段缺失均不崩溃。**

---

## 3. 新增 column 写入路径（检查 4）

| 文件 | 新列 | 谁写 | 旧 CSV 兼容 |
|------|------|------|-------------|
| `portfolio_50000_positions.csv` | `Cooldown_Until` | `process_sells` / `_run_intraday_stop` 经 `write_csv_rows(POSITION_COLUMNS)` | ✅ `POSITION_COLUMNS:61` 含该列；`DictWriter(extrasaction="ignore")` + `r.get(c,"")` 旧行写空 |
| `portfolio_50000_transactions.csv` | `Pending_Reason` | `_run_intraday_stop:720` 经 `write_csv_rows(TRANSACTION_COLUMNS)` | ✅ `TRANSACTION_COLUMNS:66` 含该列；`.get` 写空 |
| `dashboard_data.json` | `open_pct` | `dashboard_export.py` 直接计算注入 | ✅ 顶层字段，旧 JSON 缺则前端 `num()` 兜底 |
| `dashboard_data.json` | `market_relevant`（在 news 子结构） | `fetch_news.py` 由 Finnhub+AI 产出 | ✅ 旧 news 缺字段前端 KEEP |
| `portfolio_50000_target.csv` | 7 列固定（`Scan_Date,Ticker,Action,Target_Shares,Ref_Price,Stop_Loss,AI_Reason`） | `portfolio_target.py:197` | ✅ 缺持仓 CSV → `_load_held_shares/_stops` 返回 `{}`，HOLD 行 `shares=0/stop=""` 仍落盘（write 包 try/except:208） |

**结论：列写入路径全部经 `.get` + `DictWriter(extrasaction="ignore")`，旧 CSV 零破坏。**

---

## 4. 意外成功场景（检查 5）

> 不只查"会不会失败"，更查"会不会成功但结果错"。

| 场景 | 会不会真发生？ | 结果对吗？ |
|------|---------------|-----------|
| 严筛 80 真出 1 只候选 → 会真买入吗？ | ✅ 会。`strict_filter` 用 `MIN_SCORE=80`，候选经 `build_ai_input` 进 AI、再经 `to_write` 落 pending；review 全量 run 的 `process_buys` 会买（受 7天冷却/近1-2日止损/占比闸门约束） | ✅ 逻辑正确；但候选数依赖动态 R/R≥2.0 & 止损 2-5% & ≤1/板块，**可能仍为 0**（前轮已验不崩） |
| target 写 1 只 BUY → 前端显示对吗？ | ✅ 会（若候选 1 且未持仓） | ✅ `app.js:486-509` 遍历 `target.map` 渲染 Ticker/Action/数量/参考价/理由；`target_shares==null→NA`，不崩 |
| 盘中止损真触发 → 冷却生效吗？ | ✅ 会。`_run_intraday_stop` 写 `Cooldown_Until=止损日+7天`(:730) + `Pending_Reason="True"`(:720) | ✅ 冷却**生效**：`process_buys:485-489` 读 `_load_cooldowns` 跳过 `today<=cd`；单日上限 2 只(:680)；幂等 `txn_id`(:700) 防重复 |
| **意外成功陷阱**：review 与 dashboard-data 并发，review 真平仓后 positions 被 dashboard-data 的旧 positions 覆盖 | 🔴 **会**（见 H1） | ❌ **结果错**：positions 显示 OPEN 但 transactions 有 SELL → 账本不一致，下次 review 可能误判/重复卖 |

---

## 5. 风险汇总（每项含证据 + 修复方向，只列不改）

### 🔴 高危（会丢数据 / 账本不一致）

**H1 · review 全量 run 与 dashboard-data 跨 workflow 并发写 `positions.csv`/`transactions.csv`**
- **证据**：
  - 并发组独立：`review.yml:11-13` 组 `us-stock-review`；`dashboard-data.yml:38-44` 组 `dashboard-data-refresh` → GitHub **不串行**。
  - 两方都写 portfolio 文件：实际写者只有 `portfolio_50000.py`，它被 `dashboard-data.yml:86`(`--price-only`→写 positions `:773`)、`:92`(`--intraday-stop`→写 positions+transactions `:737-738`)、`review.yml:58`(全量→写 positions+transactions+history+meta) 调用。
  - 时序：`review.yml:8` cron `23 22 * * 1-5` UTC = **北京 06:23**（周一~周五盘后）；`dashboard-data.yml:16` `*/15 * * * 1-5` 每 15 分钟。22:23 UTC 落在 22:15/22:30 两个 dashboard-data 槽之间 → **必重叠**。
  - 推送模式：两方各自 `reset --soft FETCH_HEAD` 重试（review `:129-147`；dashboard-data `:175-203`），**重试不重跑 `portfolio_50000.py`**，只把本 workflow 生成的旧文件重提到最新 main → 落败方把基于旧 checkout 的 `positions.csv` 覆盖胜方变更。
  - `portfolio_50000.py:756` 注释已承认"避免与盘后 review 抢同一份账本"并让 `price_only` 跳过交易/历史写回，但 **`:773` 仍写 `positions.csv`** → 缓解不完整。
- **后果**：review 刚平仓的 `CLOSED` 状态可能被 dashboard-data 的旧 `OPEN` 版 positions 覆盖 → `positions.csv` 与 `transactions.csv` 不一致（positions OPEN 但 transactions 有 SELL）；下次 review 可能误判/重复卖。
- **首个风险窗口**：**周二 2026-10-14 06:23 北京**（处理周一 10-13 美东 scan）。周六无 dashboard-data（`1-5`），故周五 scan 的 review（周六 06:23 北京）无重叠。
- **修复方向（只列不改）**：① 将 review 与 dashboard-data 设为**同一 `concurrency.group`**（如 `portfolio-ledger`），让 GitHub 串行排队；② `dashboard-data` 的 `--price-only` 写前先 `git pull --ff-only` 拉最新 positions 再写回（合并后落盘）；③ 把"价格刷新"与"状态变更"彻底分离（价格写独立中间文件，review 后再合并）；④ review 的 push 重试中**重新跑** `portfolio_50000.py` 而非仅重提旧文件。

### 🟡 中危（噪声 / 警告 / 需运营确认）

**M1 · news-fetch 与 quant-research 兄弟 job 并发 push 同 main**
- **证据**：`scan.yml:160-172` 二者并列 `needs:scan` 并行；`news-fetch.yml:57-79` / `quant-research.yml:82-98` 各自 `reset --soft` 重试。
- **后果**：写**不相交**文件（news_data.json vs 14 个研究产物）→ **不丢数据**，但会多几次 push 失败重试（噪声/延迟）。
- **修复方向**：可接受；若想消除噪声，在 `scan.yml` 用 `quant-research: needs: news` 使二者串行。

**M2 · `scan.py:3762` 注释陈旧（仍写"评分≥90"）**
- **证据**：`scan.py:3762` `严筛候选(≤3) 评分≥90 & R/R≥2.0...`，实际 `MIN_SCORE=80`（`quant_filter.py` commit `683b45b`）。
- **后果**：非 bug，仅误导维护者。
- **修复方向**：注释改为 `≥80`。

**M3 · dashboard-data 的 `push` 触发器会在 `dashboard_export.py` 改动时额外跑一次**
- **证据**：`dashboard-data.yml:27-32` `push: paths:[dashboard_export.py,...]`；周末 `2c24885` 加 open_pct 已触发一次刷新。
- **后果**：无害，但任何 `dashboard_export.py` 改动都会多跑刷新。
- **修复方向**：无需改，仅提醒。

**M4 · `ENABLE_AI_REASON_BACKFILL="1"` 已激活 → 周一 review 真实调 AI 回填**
- **证据**：`review.yml:52` 设 flag；`review.py:3820-3824` 调 `backfill_pending_reasons`；`review.yml:58` 随后跑全量 `portfolio_50000.py`。
- **后果**：① 真实消耗 AI 配额/成本；② **需确认回填写入的 `Pending_Reason` 文本不会被随后全量 run（`:58`）覆盖/丢失**（review 自身串行内风险，非跨 workflow）。
- **修复方向**：确认 backfill 产出在 `portfolio_50000.py` run 后是否保留；若被覆盖，调整顺序或落地位置。

### 🟢 低危（观察项，已验证安全）

- **L1 字段/列向后兼容全部通过**（见 §2/§3）：`Cooldown_Until`/`Pending_Reason`/`open_pct`/`market_relevant`/`target` 旧数据均不崩。
- **L2 目标文件行数 ≠ 浮动只数 3-5**：target 反映"目标态"（持仓+候选+卖出指令，上限 ~7），与 process_buys 的当前持仓闸门是不同口径，无冲突但数值不同，避免误读。
- **L3 target 文件 7 列固定**（`portfolio_target.py:197`），缺持仓 CSV 时 `_load_*` 返回 `{}`，HOLD 行 `shares=0/stop=""` 仍正常落盘（write 包 try/except:208）。
- **L4 scan 写 target 的 commit guard 已覆盖**（`scan.yml:99-101` + `ENABLE_TARGET_FILE` 由 `scan.yml:46` 设；dashboard-data 不重复 add，分工正确）。
- **L5 0 候选不崩**（前轮已验）：`scan.py:3741` `if not pool_data: sys.exit(0)`；target `n_targets==0` 时 `build` 返回 `[]`、write 跳过（`portfolio_target.py:194-196`）；前端隐藏。
- **L6 `evolve.yml` 仅 `git push`，不写 portfolio 文件**（确认非交叉写者）。

---

## 6. 执行纪律确认

- ✅ 全程只读：`git` / `grep` / 文件读取，**未运行任何 `.py`**。
- ✅ 未改任何代码、未 push、未 rebase、未碰监控、未调 AI。
- ✅ 本报告仅列风险与修复方向，**未做任何修改**。
- 仓库当前 HEAD = `623e06f`，工作树状态以你本地 `git status` 为准（本体检未触发任何写操作）。
