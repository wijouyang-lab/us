# Options Reward/Risk 修复 — 最终生产验收报告

> 性质：**只读验收**。未修改任何文件/代码/CSV/workflow，未 commit，未 push，未手动触发任何 workflow。
> 验收时刻：UTC 2026-10-02 00:45（北京 08:45）

---

## 1. 当前部署状态

| 项 | 值 |
| --- | --- |
| 远端 `origin/main` HEAD | `f24866d`（= 我的修复 `b1c43f8` + 后续 dashboard 数据刷新） |
| RR 修复 commit `b1c43f8` | ✅ **已在远端历史中**（`git log origin/main` 命中 1 次） |
| 修复内容 | `fix(options): enforce 2.0 reward/risk gate for actionable options` |
| 远端引擎 | ✅ 含 `MIN_REWARD_RISK` / `evaluate_trade_eligibility` |
| 远端 dashboard_export | ✅ 含 `is_actionable_option` |
| 远端 app.js | ✅ 含 `isActionableOption` |

> **部署完成**：RR 门槛代码已在生产 `main` 上生效。

---

## 2. Scan 是否使用新逻辑

| 项 | 值 |
| --- | --- |
| 最新 Scan run | `#148`（schedule，`created=2026-09-30T18:21:10Z`，head_sha=`97374182`） |
| head_sha 是否含 RR 修复 | ❌ **否**（`97374182` 是 b1c43f8 之前的旧代码） |
| 2026-10-01 / 10-02 是否有新 Scan | ❌ **无**（10-01 触发点缺失，10-02 尚未到触发点） |
| 下一次 Scan 触发点 | **2026-10-02 13:07 UTC**（北京 21:07），距验收时刻约 12.5 小时 |

> ⚠️ **Scan 尚未使用新代码运行**。真实 CSV 重算需等待下一次 Scan。

---

## 3. option_strategies.csv 验证

| 检查项 | 结果 |
| --- | --- |
| 是否存在 `RewardRisk` 字段 | ✅ 存在 |
| 是否存在 `Reject_Reason` 字段 | ❌ **不存在**（当前 56 列；新代码会追加为 57 列） |
| 总行数 | 10 |
| Status 分布 | `Active` × 10（**旧数据，尚未重算**） |
| Strategy 分布 | SHORT_PUT × 5，CALL_DEBIT_SPREAD × 5 |
| Active 是否全满足 RR ≥ 2.0 | ❌ **否**（但这是旧数据，非新逻辑产物） |
| RR < 2.0 是否变为 Rejected | ❌ **否**（旧数据仍为 Active） |

### 真实案例（ALL SHORT PUT）

| 字段 | 当前 CSV 值（旧数据） | 新逻辑预期 |
| --- | --- | --- |
| Strike | 210.0 | — |
| Premium | 3.70 | — |
| Max Profit | 370.0 | — |
| Max Loss | 20630.0 | — |
| Reward/Risk | 空（旧代码不计算） | ≈ 0.0179 |
| Status | **Active**（旧） | **Rejected** |
| Reject_Reason | 无此列 | `Reward/Risk below 2.0` |

> **结论**：CSV 仍是旧代码产物（`Reject_Reason` 列缺失、Status 全 Active）。新逻辑已通过离线推演验证会正确判定该案例为 Rejected（raw RR = 0.017935046），但**生产 CSV 尚未重写**——**等待下一次 Scan**。

---

## 4. Review 验证

| 检查项 | 结果 |
| --- | --- |
| 是否只处理 Active 策略 | ✅ 是。`review.py` 多处按 `Status == "Active"` 严格过滤（line 918 / 942 / 1420 / 1444 / 1467） |
| Rejected 是否进入持仓逻辑 | ✅ 不会。`Status="Rejected"` 不匹配 Active 过滤条件 |
| 是否修改 review.py | ❌ 未修改（本次验收只读，且历史实现本就正确） |

> Review 过滤逻辑正确，Rejected 不会成为新的 Active Option Position。
> （历史遗留的 `Status=Active` 旧记录仍会被 Review 视为持仓，待 Scan 重算 CSV 后自动消除。）

---

## 5. Dashboard 验证

| 检查项 | 结果 |
| --- | --- |
| Actionable Options 是否只显示 Active | ✅ 是。`options[] = 0`（当前无任何 RR ≥ 2.0 的记录） |
| RR < 2 的策略是否被隐藏 | ✅ 是。10 条旧记录（RR 0.018–1.44 或为空）全部被过滤 |
| `rejected_options_count` 是否正确 | ✅ 正确 = **10** |
| `active_options_count` | ✅ = **0** |
| Dashboard 数据与 CSV 一致 | ⚠️ 见下方说明 |

### Dashboard 与 CSV 的"一致性"说明

| 口径 | 值 | 说明 |
| --- | --- | --- |
| CSV 底层 `Status` 字段 | 10 条 `Active`（旧值） | 未重算，等待 Scan |
| Dashboard `options[]`（Actionable） | **0 条** | 通过 `is_actionable_option`（含 RR ≥ 2.0 校验）过滤 |
| Dashboard `rejected_options_count` | **10** | 同上，RR < 2.0 或 unavailable 均计入 |

> Dashboard 的过滤**比 CSV 的 Status 字段更严格**（额外校验 RR ≥ 2.0），因此即便 CSV 尚未重算，
> Dashboard 也已正确屏蔽了全部 RR < 2.0 的历史记录。这是**符合预期**的防御性过滤行为。
> Scan 重算后，CSV 的 Status 字段会与 Dashboard 口径完全对齐。

---

## 6. Email 是否完全移除

### 全仓库搜索结论

| 搜索关键词 | 结果 |
| --- | --- |
| `smtplib` / `SMTP` / `SMTP_SSL` | ❌ **无任何命中**（全仓库 `.py`） |
| `send_mail` / `send_email` | ❌ 无命中 |
| `MIMEMultipart` / `MIMEText` | ❌ 无命中 |
| `mail notification` | ❌ 无命中 |
| Python 读取 `EMAIL_ACCOUNT` / `EMAIL_PASSWORD` / `TARGET_EMAILS` | ❌ 无命中（scan.py / review.py 均不再读取） |
| 邮件发送函数（def *mail / def *email / notify 等） | ❌ 无命中 |

### 仍存在 Email 痕迹（仅配置残留，非生产路径）

| 文件 | 内容 | 性质 |
| --- | --- | --- |
| `.github/workflows/scan.yml` | `TARGET_EMAILS/EMAIL_ACCOUNT/EMAIL_PASSWORD` secrets 注入 | ⚠️ 遗留配置（环境变量注入，但 Python 已不再读取） |
| `.github/workflows/review.yml` | 同上 | ⚠️ 遗留配置 |
| `.github/workflows/evolve.yml` | 同上 | ⚠️ 遗留配置 |

> **结论**：Email **生产代码路径已完全移除**（无 SMTP 客户端、无发送函数、无环境变量读取）。
> 仅剩 3 个 workflow 文件里的 secrets 注入属于**无害遗留配置**——环境变量被注入但无人消费，不会发送任何邮件。
> 本次验收未删除这些配置（遵循"只读、不修改"）。

---

## 7. 最终验收标准核对

| 验收项 | 结果 |
| --- | --- |
| 部署版本包含 RR 修复 | ✅ 通过（`b1c43f8` 已在 `origin/main`） |
| 引擎 RR 门槛（2.0）已部署 | ✅ 通过 |
| Dashboard Actionable 过滤已生效 | ✅ 通过（线上 options=0，rejected=10） |
| Review 只处理 Active / 拒绝 Rejected | ✅ 通过（源码过滤正确） |
| Email 生产路径移除 | ✅ 通过（无发送代码） |
| **Scan 已用新代码重算 CSV** | ⏳ **未完成**（触发点 13:07 UTC，约 12.5 小时后） |
| CSV 含 `Reject_Reason` 列 | ⏳ 未完成（等待 Scan） |
| 真实案例（ALL 210/3.70）在生产 CSV 中变 Rejected | ⏳ 未完成（等待 Scan） |

---

## 最终结论

# ⏳ 等待下一次 Scan 生产数据验证

### 已达到的部分（生产验收标准的前半段）

- ✅ **部署完成**：RR 修复 `b1c43f8` 已在生产 `main` 生效
- ✅ **Dashboard 链路验证通过**：真实数据 → 0 Actionable / 10 Rejected，线上页面已生效
- ✅ **Review 链路验证通过**：按 Status 过滤，Rejected 不进入持仓
- ✅ **Email 生产路径已完全移除**

### 尚未达到的部分（受 Scan 触发时间约束）

- ⏳ **CSV 生产数据重算**：`option_strategies.csv` 仍是旧代码产物（无 `Reject_Reason` 列、10 条 Active）
- 下一次 Scan 触发点 **2026-10-02 13:07 UTC**（北京 21:07），届时新引擎将重算 CSV，旧记录变为 `Rejected`、追加 `Reject_Reason` 列，真实案例 ALL（210/3.70）将由 Active 转为 Rejected。

### 备注

- Stage 6B/6C 已观察到 Scan schedule 存在延迟（9/30 延迟 321 分钟）甚至缺失（10/01 无 run）的异常。
- 若 13:07 UTC 之后仍无 Scan run，CSV 重算将进一步推迟，属 schedule 问题，与本 RR 修复无关。
- **本次验收未修改任何文件、未 commit、未 push、未手动触发 workflow。**
