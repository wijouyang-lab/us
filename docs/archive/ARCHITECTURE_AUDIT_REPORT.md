# Read-Only Architecture Audit

> 性质：**只读审计**。未修改任何代码/配置/workflow/数据，未删除文件，未 commit/push/dispatch。
> 审计时刻：UTC 2026-10-02 02:10（北京 10:10）

---

## 1. Current HEAD

| 项 | 值 |
| --- | --- |
| HEAD | `b1c43f8dd41910aa339ec0d1bcf3e1d94c325b3d`（`fix(options): enforce 2.0 reward/risk gate for actionable options`） |
| 远端 `origin/main` | `f24866d`（HEAD + 后续 dashboard 数据刷新） |
| 工作区 | 干净（仅 untracked `__pycache__/`，无业务文件修改） |

---

## 2. Production Commit Verification

| Commit | 用途 | 在历史中 |
| --- | --- | --- |
| `b1c43f8` | Options RR 门槛（本次审计对象） | ✅ |
| `7bfb6d5` | Runtime latest + last_success 升级 | ✅ |
| `5d65f84` | Runtime collector 触发修复 | ✅ |
| `7724e03` | Scan cron 避开整点（0 13 → 7 13） | ✅ |
| `dd11d91` | 显式 UTC schedule | ✅ |
| `61de4fc` | 引入 GitHub native schedule | ✅ |

> 所有关键生产 commit 均在历史中，无回退。

---

## 3. Actual Data Flow

基于实际 `import` / `read_csv` / `to_csv` / workflow 证据建立的真实数据流：

```
scan.py  (Tag == "Core_Dragon" 时调用)
  ├─ import scan_us_option_engine (append_option_strategy)     [scan.py:44]
  ├─ 写 us_stocks_pending_YYYYMMDD.csv                          [scan.py:3795]
  ├─ 写 trade_history.csv                                       [scan.py:2315-2515]
  ├─ 写 option_strategies.csv（经 engine）                      [engine:23,735]
  └─ 写 ai_text_cache.csv / ai_snapshot.csv                    [scan.py:3399,3471]
          ↓
review.py
  ├─ 读 us_stocks_pending_*.csv (+.processed)                  [review.py:471,541]
  ├─ 读写 trade_history.csv（持仓/止损/平仓）                    [review.py:376,1433]
  ├─ 读 option_strategies.csv（期权持仓，Status=Active）          [review.py:378,918]
  └─ 写 review_history.csv（每日快照/里程碑）                   [review.py:377,2068]
          ↓
dashboard_export.py  (dashboard-data.yml 每 15 分钟运行)
  ├─ 读 us_stocks_pending / trade_history / option_strategies / review_history / ai_*  [dashboard_export.py:71-105]
  ├─ 写 dashboard/data/dashboard_data.json                      [workflow --out]
  └─ 写 us-market-terminal/dashboard/data/dashboard_data.json（mirror）  [dashboard_export.py:2765]
          ↓
app.js  (GitHub Pages 根目录)
  └─ fetch dashboard/data/dashboard_data.json → renderOptions（含 isActionableOption 过滤）
```

**确认**：数据流闭环一致，无断裂；各层 CSV/JSON 路径与实际读写一致（非文件名猜测）。

---

## 4. Options Reward/Risk

| 项 | 结果 |
| --- | --- |
| `MIN_REWARD_RISK = 2.0` | ✅ 存在（`scan_us_option_engine.py:42`） |
| `MIN_SPREAD_REWARD_RISK = 0.40` | ✅ 仍保留（`scan_us_option_engine.py:30`），**未被替换成 2.0** |
| 两概念分离 | ✅ 0.40 = 价差 candidate selection（line 517）；2.0 = final actionable gate（line 139） |

| 策略 | MaxProfit | MaxLoss | RR 定义 | 最终 gate |
| --- | --- | --- | --- | --- |
| SHORT_PUT | premium×100×qty | (strike−premium)×100×qty | MaxProfit/MaxLoss | ✅ 经过 |
| CALL_DEBIT_SPREAD | (width−debit)×100×qty | debit×100×qty | MaxProfit/MaxLoss | ✅ 经过 |
| LONG_CALL | None（无可靠目标） | premium×100 | unavailable → Rejected | ✅ 经过 |

- **raw gating**：`evaluate_trade_eligibility` 用 `theoretical_reward_risk`（原始浮点，line 95-153），CSV 落库 10 位精度，Dashboard 不 round —— **无 rounded gating**。
- **MaxProfit/MaxLoss 公式未被篡改**：`max_loss = max(0, effective_entry)*100`（`(strike−premium)×100`）原样保留。
- **未伪造 Planned Risk**：StopLoss 仍为纯文本（"无固定技术止损…"），无数值止损字段。
- **RewardRisk unavailable → 不能 Active**：`rr is None` 返回 `("Rejected", None, "Reward/Risk unavailable")`。

### ALL 210 / 3.70 案例（离线推演，真实代码路径）

```
MaxProfit = 3.70 × 100 = 370
MaxLoss   = (210 − 3.70) × 100 = 20630
RewardRisk = 370 / 20630 = 0.017935046  →  < 2.0
Status = Rejected   Reject_Reason = "Reward/Risk below 2.0"
```
✅ 符合预期。

---

## 5. CSV Schema Consistency

| CSV | 写入方 | 读取方 | 关键字段一致性 |
| --- | --- | --- | --- |
| option_strategies.csv | engine（56→57 列，含 Reject_Reason） | review.py / dashboard_export.py | ✅ 字段名一致（Ticker/Strategy/Status/RewardRisk/MaxProfit/MaxLoss/Reject_Reason） |
| trade_history.csv | scan.py / review.py | review.py / dashboard_export.py | ✅ |
| review_history.csv | review.py | review.py / dashboard_export.py | ✅ |
| us_stocks_pending_*.csv | scan.py | review.py / dashboard_export.py | ✅ |

- 空值处理：全部 `dtype=str, keep_default_na=False` + `parse_num`/`safe_float` 统一转 None。
- 数字：统一 `parse_num`（去除 `$`,`,`,`%`）；NaN/inf 由 `_safe_num`/`safe_float` 过滤。
- 日期：统一 `pd.to_datetime(..., format="mixed")` + `normalize_date`。
- **未发现跨层重算覆盖导致的字段不一致**。

---

## 6. Review Active/Rejected Handling

| 检查项 | 结果 |
| --- | --- |
| 进入持仓/风控/盈亏/统计的条件 | ✅ `Status == "Active"` 严格过滤（`review.py:918` 期权，`681` is_active_holding 股票） |
| Rejected 是否创建持仓 | ✅ 不会（`Status="Rejected"` 不匹配 Active 过滤） |
| Rejected 是否进入止损/胜率 | ✅ 不会 |
| Rejected 是否保留供审计 | ✅ 保留在 `option_strategies.csv` 底层 |

> Rejected 数据被完整保留，仅不进入 actionable 持仓/统计口径，符合设计。

---

## 7. Scan → Review Price/PnL Consistency

| 项 | 结论 |
| --- | --- |
| 正式买入价定义 | ✅ `safe_record_price`（`review.py:424-431`）= trade_history 的 `Price` 字段 = **推荐日真实 Open** |
| 是否 fallback 到 Scan_Ref_Price / Close / 实时价 | ✅ **禁止**（注释 + 代码明确：Open 未产生 → None 等回补） |
| PnL 公式 | ✅ `pnl = round((cur − rec_price)/rec_price×100, 2)`（`review.py:1711`、`1887`） |
| 推荐价回填 | ✅ `backfill_rec_price()` 从 review_history / pending 取 Rec_Date 真实 Open 幂等回填 |

> **未发现** Open→Close 正负号反转、未来价格、错误日期、pct_change 误用、时区错位等过去问题。价格口径已修复并保持一致。

---

## 8. Stop-Loss Lifecycle

| 检查项 | 结果 |
| --- | --- |
| 止损触发是否真正退出持仓 | ✅ 是。`update_trade_history_status(..., "Stop_Loss_Hit", exitp)`（`review.py:1831`）设置 `Status="Stop_Loss_Hit"` + `Exit_Date` |
| Exit_Price / Exit_Date 是否进入历史 | ✅ 是（写入 trade_history 对应行） |
| 止损股是否误重入持仓 | ✅ 不会。`is_active_holding`（`review.py:681`）只认 `Status ∈ {"", "Active", "pending"}` 且 `Exit_Date` 为空；`Stop_Loss_Hit` 不匹配 |
| 状态区分 | ✅ ACTIVE / Stop_Loss_Hit / CLOSED 等，`Review_Risk_Status` 另记 `STOP_TRIGGERED` |
| 同日 Entry→Stop→Close 顺序 | ✅ 止损价取值有明确优先级（Gap Down 取 Open，否则取 Stop；`review.py:755-756`） |

> 止损生命周期闭环正确。注：存在 `Status`（Stop_Loss_Hit）与 `Review_Risk_Status`（STOP_TRIGGERED）双状态字段，属设计（主线状态 + 风险联动），未发现混淆导致错误。

---

## 9. Recommendation History

| 检查项 | 结果 |
| --- | --- |
| 事件唯一键 | ✅ `review_event_key`（`review.py:2051`）= Rec_Date + Ticker + Tag + 期权区分字段 |
| 同一股票多次推荐分别计数 | ✅ 是（不同 Rec_Date 或不同 Tag = 不同 event） |
| 推荐日期保留 | ✅ Rec_Date 保留 |
| 去重幂等 | ✅ 写入 review_history 前按 event key 定位更新 |

---

## 10. Win Rate Calculation

实际公式（`compute_milestone_win_rate`，`review.py:2336-2366`）：

```
Win  = PnL_N > 0
Loss = PnL_N <= 0（含 0）
Eligible = Wins + Losses（仅"已有有效 PnL_N"的记录进入分母）
PnL_N 缺失/未达标/Rec_Price 缺失 → 不进入分母（None 跳过）
win_rate = Wins / Eligible × 100
Eligible == 0 → None（前端显示 N/A）
```

| 检查项 | 结果 |
| --- | --- |
| 未结束持仓是否进入分母 | ✅ 不进入（PnL 未达标为 None，跳过） |
| Rejected / Cancelled 是否进入 | ✅ 不进入 |
| Stop-loss 是否正确计 Loss | ✅ 止损结算价 → PnL ≤ 0 → Loss |
| 同日推荐是否重复统计 | ✅ 按 event key 去重 |
| Options 是否混入股票胜率 | ✅ 不混入（见第 11 节） |

---

## 11. Stock vs Options Performance

| 项 | 结果 |
| --- | --- |
| 股票胜率 | ✅ milestone win rate（5D/10D/20D，`compute_milestone_win_rate`） |
| 期权胜率 | ✅ 独立计算（`review.py:3189-3193`：`option_wins / len(option_closed_pnl)`，来源为 option_strategies.csv 的 realized PnL） |
| 两者是否分离 | ✅ 明确分离（代码注释 `review.py:11`"期权完全独立，不混入股票 Scan 推荐胜率"） |

> 期权有 realized PnL（平仓时写入 `PnL` 字段）与 unrealized PnL（持仓风险监控）。股票胜率与期权胜率分账，无混合。

---

## 12. Dashboard Actionable Filtering

| 项 | 结果 |
| --- | --- |
| Active 才 actionable | ✅ `is_actionable_option`（`dashboard_export.py:1617`）：`status=="active"` 且 `reward_risk>=2.0` |
| Rejected 不显示为可执行 | ✅ 被过滤 |
| `options[]` / `active_options_count` / `rejected_options_count` 逻辑一致 | ✅ 三者同源（`all_options` 全量 → 过滤得 active/rejected） |
| 全部被拒绝时状态 | ✅ `options[]=0, active=0, rejected=10` 属**合理状态**（当前生产数据即此状态） |

---

## 13. Dashboard Runtime Regression

| 项 | 结果 |
| --- | --- |
| Runtime schema | ✅ `latest` + `last_success` + `error`（`fetch_runtimes.py:7-36`） |
| 是否回归 `?status=success` 旧逻辑 | ✅ 未回归（grep 无匹配） |
| 状态覆盖 | ✅ queued/in_progress/success/failure/cancelled/skipped/no-data（`_build_latest` 保留原始 status/conclusion） |
| 前端 polling | ✅ `setInterval(refreshRuntime, 60000)` 仍存在 |
| dashboard-data.yml 监听 fetch_runtimes.py | ✅ push.paths 含 `dashboard/fetch_runtimes.py` |

---

## 14. Old Dashboard / Dead Code

| 文件/目录 | 是否被引用 | 是否 production path | 定性 |
| --- | --- | --- | --- |
| `us-market-terminal/index.html` | 无（跳转页） | ❌ | 旧入口残留（redirect 到 `../`） |
| `us-market-terminal/assets/app.js`（1121 行，无 isActionableOption） | 无 | ❌ | **旧版前端**，dead |
| `us-market-terminal/assets/app.css` | 无 | ❌ | 旧版样式，dead |
| `us-market-terminal/dashboard/data/dashboard_data.json` | 无（旧数据 10 条 Active） | ❌ | 旧数据镜像 |
| `review_kpi_simplify_v25.py` | 无 | ❌ | dead |
| `review_kpi_tracking_fix.py` | 无 | ❌ | dead |
| `tencent_scf_review_trigger.py` | 无 | ❌ | 旧调度方案（腾讯云 SCF）残留 |
| `patch_v34.py` | 无 | ❌ | 一次性补丁残留 |
| `ai_router.py` | 无 import | ❌ | dead（疑似） |
| `clawsocket_compat.py` | ✅ 被 scan/evolve/probe 引用 | ✅ | production |
| `clawsocket_probe.py` | 无直接 import | 部分 | 工具脚本 |

### 关键风险：dashboard_export.py 的旧 mirror write

- `dashboard_export.py:2435-2436`：默认 `--out` 未指定时，优先写 `us-market-terminal/dashboard/data/`
- `dashboard_export.py:2765-2769`：`--no-mirror` 未加时，同步镜像写 `us-market-terminal/dashboard/data/`
- workflow 未加 `--no-mirror`，且 commit 步骤 `git add us-market-terminal/dashboard/data/dashboard_data.json`
- **影响**：每次 dashboard-data 运行都会向已废弃的旧前端路径写一份数据，并 commit 到仓库 → 重复写入 + 死数据维护负担。

---

## 15. Email Removal Verification

| 搜索 | 结果 |
| --- | --- |
| smtplib / SMTP / send_mail / send_email / MIMEText / MIMEMultipart / mail notification | ❌ 全仓库无命中 |
| scan.py / review.py 读取 EMAIL_* 环境变量 | ❌ 无命中 |
| 邮件发送函数 | ❌ 无 |

> Email 生产代码路径已完全移除。仅剩 3 个 workflow 注入 `EMAIL_ACCOUNT/EMAIL_PASSWORD/TARGET_EMAILS` secrets，属 **stale configuration**（注入但无人消费）。当前业务链路以 **Scan → CSV → Review → Dashboard** 为准，不含 Email。

---

## 16. Workflow / Concurrency Risks

| workflow | concurrency | cancel-in-progress | 风险 |
| --- | --- | --- | --- |
| dashboard-data | `dashboard-data-refresh` | **true** | ⚠️ **stale data 覆盖**（见下） |
| scan | `us-stock-scan` | false | 无（排队等待） |
| review | `us-stock-review` | false | 无（排队等待） |

### dashboard-data concurrency stale-data 风险（已实际发生过一次）

- **证据**：2026-10-02 部署 Options RR 时，旧代码 run（`36946296514`）与 push run（`36946306585`）并发，旧 run 抢先提交旧数据（10 条 Active），新 run 的正确数据（0 条）push 被拒绝、重试 3 次失败后被丢弃。
- **发生条件**：`cancel-in-progress: true` + 两个 run 几乎同时触发（schedule `*/15` 与 push 撞车）。
- **现有保护**：commit 步骤有 `pull --rebase` 重试 3 次；但重试仍可能因 rebase 冲突/非 fast-forward 失败（当时即失败）。
- **结论**：`cancel-in-progress: true` 允许新 run 取消旧 run，但**旧 run 若已进入 commit 阶段**仍可能抢先写脏数据。属 P1 潜在风险（会短暂产生错误 Dashboard 数据，需人工重新 dispatch 修正）。**本次审计未修改。**

---

## 17. Schedule Status

| workflow | cron（UTC） | 北京 | 确认 |
| --- | --- | --- | --- |
| Scan | `7 13 * * 1-5` | 周一~周五 21:07 | ✅ |
| Review | `0 22 * * 1-5` | 周二~周六 06:00 | ✅ |
| Evolve | `0 2 * * 6` | 周六 10:00 | ✅ |
| Dashboard-data | `*/15 * * 1-5` | 每 15 分钟 | ✅ |

> **Production RR validation pending**：`2026-10-02 13:07 UTC` 的自然 Scan 尚未发生（距审计时刻约 11 小时）。CSV 仍是无 `Reject_Reason` 列的旧数据。**未手动 dispatch，未改 schedule。**

---

## 18. Findings

### P0（错误交易/持仓/错误生产结果）

无。

### P1（统计/胜率/Review/Dashboard 错误风险）

| # | Severity | File:Line | Evidence | Impact | Recommended fix（不执行） |
| --- | --- | --- | --- | --- | --- |
| P1-1 | P1 | `.github/workflows/dashboard-data.yml:38-40` | `concurrency.cancel-in-progress: true`；曾致旧 run 抢先提交旧数据、新 run 正确数据被丢弃（run 36946296514 vs 36946306585） | Dashboard 短暂显示陈旧 options 数据 | 评估改为 `cancel-in-progress: false` 或在 commit 阶段增加更强重试/冲突保护 |

### P2（架构风险/重复逻辑/维护问题）

| # | Severity | File:Line | Evidence | Impact |
| --- | --- | --- | --- | --- |
| P2-1 | P2 | `dashboard_export.py:2435-2436, 2765-2769` | 默认优先写 + mirror 写 `us-market-terminal/dashboard/data/`；workflow 未加 `--no-mirror` 且 commit 该路径 | 每次运行向废弃旧前端写死数据并入库 |
| P2-2 | P2 | `us-market-terminal/`（4 个 tracked 文件） | 旧版 app.js（无 isActionableOption）、旧 dashboard_data.json（10 条 Active）仍 tracked | 旧前端若被直接访问会看到未过滤数据 |
| P2-3 | P2 | `review_kpi_simplify_v25.py` / `review_kpi_tracking_fix.py` / `tencent_scf_review_trigger.py` / `patch_v34.py` / `ai_router.py` | 全仓库无 import/调用 | dead code，维护噪音 |

### P3（dead code/旧配置/非功能）

| # | Severity | File:Line | Evidence | Impact |
| --- | --- | --- | --- | --- |
| P3-1 | P3 | `scan.yml:43-45` / `review.yml:45-47` / `evolve.yml:66-68` | 仍注入 `TARGET_EMAILS/EMAIL_ACCOUNT/EMAIL_PASSWORD` secrets，但 Python 无读取 | 无功能影响，仅配置残留 |
| P3-2 | P3 | `us-market-terminal/index.html` | 旧入口跳转页（redirect 到 `../`） | 无害，但属旧架构残留 |

---

## 19. Recommended Next Actions

（仅建议，本次不执行）

1. **P1-1**：评审 dashboard-data 的 concurrency 策略，降低 stale-data 概率。
2. **P2-1/P2-2**：评估是否彻底下线 `us-market-terminal/`（前端改由仓库根目录承载后，旧镜像已无存在必要），并在 workflow 加 `--no-mirror`。
3. **P2-3**：确认 dead code 脚本无保留价值后归档/删除。
4. **P3-1**：清理 workflow 中已无消费者的 Email secrets 注入。
5. **待 Scan**：`2026-10-02 13:07 UTC` 自然 Scan 完成后，做 Options RR 的最终生产数据验收（CSV 出现 `Reject_Reason` 列、旧记录变 Rejected）。

---

## OVERALL STATUS

# PASS WITH WARNINGS

- **核心业务闭环正确**：数据流一致、Options RR 门槛正确、价格/PnL 口径正确（Open 基准）、胜率公式正确且 Stock/Options 分离、止损真正退出、Dashboard 过滤正确、Runtime 无回退、Email 已移除。
- **无 P0 问题**。
- **Warnings**：1 个 P1（dashboard-data concurrency stale-data 风险，已发生过一次）、若干 P2/P3（旧前端镜像 us-market-terminal 仍 tracked 且每次写入、dead code 脚本、Email 遗留 secrets）。
- **Production RR validation 仍 pending**（等待 2026-10-02 13:07 UTC 的自然 Scan）。

---

## 只读性确认

| 项 | 结果 |
| --- | --- |
| Files modified | **0** |
| Commits created | **0** |
| Pushes | **0** |
| Workflow dispatches | **0** |
| Production data mutations | **0** |

（全程仅执行 git 只读查询、grep、文件读取、纯只读内存分析；未写回任何文件。）
