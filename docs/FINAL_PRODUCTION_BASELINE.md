# FINAL PRODUCTION BASELINE

> End-to-End Final Acceptance 结果：**PASS**
> 基线生成时间：2026-09-30（北京时间）

---

## 1. Git Commit

| 项 | 值 |
|---|---|
| 最终 main HEAD | `f8cc89d3193c5b7c8f4846ab805df4a623133d0b` |
| local == origin/main | ✅ 一致 |
| working tree | ✅ clean |

关键历史提交（功能里程碑）：
- `19021f6` — P3.5 Rec_Price 确定性修正
- `06a44d4` — Dashboard Runtime + Email Removal
- `b469fd3` — P2 event key + orphan repair
- `d970140` — P1 milestone win rate
- `60f0466` — P0 动态持仓止损安全
- `ae43a86` — P0 Rec_Price fail-closed + 1225 恢复

---

## 2. Scan Workflow

- 文件：`.github/workflows/scan.yml`（name: 美股盘中扫描）
- 触发：`workflow_dispatch` + schedule cron `0 13 * * 1-5`
- 输出：`us_stocks_pending_YYYYMMDD.csv`（pending 推荐）

## 3. Review Workflow

- 文件：`.github/workflows/review.yml`（name: 美股盘后复盘）
- 触发：`workflow_dispatch` + schedule cron `0 22 * * 1-5`
- 输出：`trade_history.csv` / `review_history.csv` / `report.html` / `review_report.html`

## 4. Evolve Workflow

- 文件：`.github/workflows/evolve.yml`（name: US-Share Evolve）
- 触发：`workflow_dispatch` + schedule cron `0 2 * * 6`（含每月第一个周六 gate）

## 5. Dashboard Workflow

- 文件：`.github/workflows/dashboard-data.yml`（name: Dashboard Data Refresh）
- 触发：`workflow_dispatch` + schedule cron `*/15 * * * 1-5` + push（dashboard_export.py / summarize_run.py / dashboard-data.yml 变更）
- 输出：`dashboard/data/dashboard_data.json` + `last_run.json` + `last_run.log`

---

## 6. Scan Schedule

- UTC 13:00（cron `0 13 * * 1-5`）= 北京时间工作日 21:00

## 7. Review Schedule

- UTC 22:00（cron `0 22 * * 1-5`）= 北京时间次日 06:00

## 8. Evolve Schedule

- UTC 周六 02:00（cron `0 2 * * 6`）= 北京时间周六 10:00（仅每月第一个周六，workflow_dispatch 不受限）

> 说明：3 个 workflow 均保留 `workflow_dispatch`。腾讯云 SCF 侧定时器需在腾讯云控制台人工确认停用（GitHub 仓库内已无 SCF 触发引用，`tencent_scf_review_trigger.py` 为独立云端脚本，不在 GitHub Actions 链路内）。

---

## 9. Dashboard Runtime Architecture

`dashboard_data.json` 顶层新增独立字段 `runtimes`：

```json
{
  "scan":   {"last_success_at": "...", "last_success_sha": "...", "run_id": ...},
  "review": {"last_success_at": "...", "last_success_sha": "...", "run_id": ...},
  "evolve": {"last_success_at": "...", "last_success_sha": "...", "run_id": ...}
}
```

- 数据来源：`dashboard/fetch_runtimes.py` → GitHub Actions API（`/actions/workflows/{scan,review,evolve}.yml/runs?status=success&per_page=1`）
- 只接受 `conclusion == success`；失败/cancelled/skipped 不覆盖成功时间
- `last_success_sha` = 该成功 run 实际 `head_sha`（前 12 位）
- 前端 `index.html` 顶部 SCAN/REVIEW/EVOLVE 三卡独立显示，时间用 `toBeijingTime()`（UTC+8 固定，不依赖浏览器时区），格式 `YYYY-MM-DD HH:mm:ss`
- 旧字段 `generated_at` / `market_updated_at` / `technical_updated_at` 保留兼容

---

## 10. Email Status

**生产邮件发送已删除。**

- `review.py`：删除 `send_mail()` + `import smtplib` + `email.mime.*` import
- `scan.py`：删除 `send_mail()` + `SUPER_ADMIN`/`TARGET_EMAILS` 强制检查 + `import smtplib` + `email.mime.*` import + 3 处调用
- 保留：`build_full_email_html()`（HTML 生成）、`get_review_risk_linkage_warning()`（Scan↔Review 风控联动）、`build_review_risk_banner_html()`
- 全仓库 `smtplib`/`send_mail`/`SUPER_ADMIN`/`TARGET_EMAILS`/`EMAIL_ACCOUNT`/`EMAIL_PASSWORD` 引用数 = 0

---

## 11. AI Score Architecture

- AI 评分来源：`AI_SCORE_MAP`（`<!--AI_SCORE_MAP_START-->` / `<!--AI_SCORE_MAP_END-->` 包裹的 JSON，0~100 整数）
- 提取：优先显式定界符，回退 `{"AI_SCORE_MAP"` 文本定位
- Final Score 公式：`Final = round(0.7 * Quant_Score + 0.3 * AI_Score, 1)`
- AI Score missing / invalid → `Score` 留空（fail-closed），**绝不用 Quant 顶替 AI**

---

## 12. Milestone Architecture

- 第 N 交易日 = `Rec_Date` 之后第 N 个真实交易日（`date > Rec_Date` 升序 `iloc[n-1]`）
- `Price_N` = 该真实交易日 Close
- `PnL_N = round((Price_N - Rec_Price) / Rec_Price * 100, 2)`
- CLOSED/OPEN 状态不改变 milestone 价格（客观第 N 交易日收盘）

## 13. Win Rate Architecture

Win = `PnL_N > 0`；Loss = `PnL_N <= 0`；Eligible = 有有效 `PnL_N` 的事件数。

| Milestone | Eligible | Wins | Losses | Win Rate |
|---|---|---|---|---|
| 5D | 141 | 66 | 75 | 46.81% |
| 10D | 110 | 54 | 56 | 49.09% |
| 20D | 56 | 29 | 27 | 51.79% |

N/A / 未达标 / Rec_Price 缺失 / Price_N 缺失 → 不进入分母。

---

## 14. Stop Loss Architecture

- Active holdings = 完整 `trade_history` 中 `Status ∈ {空,Active,pending}` 且 `Exit_Date` 空的持仓，**不受 30 天 cutoff 限制**
- 当前有效 Stop_Loss = 生命周期内最新有效值（不回退更低技术候选）
- 触发规则（统一快照 + 当前有效 Stop_Loss）：
  1. Stop_Loss 无效 → 不触发，仅 warning
  2. `Low <= Stop_Loss` → STOP_TRIGGERED
  3. Low 缺失但 `Close <= Stop_Loss` → STOP_TRIGGERED（Close 已证明破位）
  4. Low/Close 都缺失 → DATA_MISSING（不猜测）
  5. Gap-down（`Open < Stop_Loss`）→ Exit = Open；否则 Exit = Stop_Loss
- `is_valid_existing_stop`：`MAX_TRAILING_RATIO=2.0`，异常历史止损不进入 `max(old, candidate)` floor
- 每持仓输出 `[风控诊断]`（Trade_Date/Open/High/Low/Close/Stop/Trigger/Exit/OHLC_Source）
- 历史异常 Stop_Loss 已在 P0.5 修复（15 条），`scan.py` 写入侧新增 `_is_valid_ai_stop` 拦截

## 15. Event Key Architecture

```python
review_event_key = (Rec_Date, Ticker.upper(), Tag, Option_Type.upper(), Strike, Expiry)
```

- 同一 `(Rec_Date, Ticker, Tag)` = 同一 logical event
- `Review_Date` / `Status` / 行号 / dataframe 顺序 **不参与** event identity
- 同一 event 多个 Review snapshot 共享同一 key
- `append_review_rows` 的 pos 逻辑覆盖为最新快照（不取首行）

## 16. Rec_Price Architecture

- `Rec_Price = Rec_Date` 真实 Open（`safe_record_price` = trade_history `Price` 字段）
- OHLC 获取失败且已有有效 Rec_Price → **保留原值**（fail-closed，不清空）
- OHLC 获取失败且无有效 Rec_Price → 保持空（不猜测/不估算）
- P3.5 已完成 7 个历史 Rec_Price 修正（NCLH/HAL/OXY/T/GEN/PPL/UBER）

---

## 17. Current Known Exceptions

以下为**已审计确认、不修改**的历史数据项，不得在后续工作中重新制造：

1. **Trap_Warning orphan（12 event / 24 行）**：诱多对照组，review.py 不追踪其生命周期，空 Status 符合数据模型。
2. **Observation/Core_Dragon unresolved orphan（30 event / 59 行）**：历史英文 Status 无法唯一映射中文（一对多），且回补会改变 KPI 口径，按「不猜」保留。
3. **KLAC/ROST/UPS 浮点噪声（3 个 Rec_Price collision）**：round(6) 后为同一价格，纯浮点尾数表示差异，非数据错误，不修。
4. **腾讯云 SCF 定时器**：GitHub 侧已无重复触发，但 SCF 云端定时器需在腾讯云控制台人工停用（超出 GitHub 权限）。

---

## Final Acceptance 判定

- Repository clean ✅
- 全量测试（11 个测试文件）✅
- Scan→Pending→Review→Dashboard 链路 ✅
- AI Score / Milestone / Win Rate ✅
- Stop Loss / Rec_Price / Event Key ✅
- Dashboard Runtime（独立 scan/review/evolve）✅
- Schedule（scan 21:00 / review 06:00 / evolve 周六 10:00 北京）✅
- Email removal（0 引用）✅
- Production workflow success（Review run `36688871161` = success；Dashboard-data run `36686790055` = success）✅

**FINAL ACCEPTANCE = PASS**
