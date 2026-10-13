# 触发架构总文档（Trigger Architecture）

> 背景：调查发现 `scan.yml` **没有 schedule**（仅 `workflow_dispatch`），而 `dashboard-data.yml` 的
> schedule 正常工作。本文汇总所有 workflow 的触发结构、设计规则与外部触发方案。
> 本文档为**只读汇总 + 设计**，不实施、不触碰仓库任何文件。

---

## 1. 现状表（所有 `.github/workflows/*.yml` 的 `on:` 段）

> 数据来源：前次只读调查（`SCHEDULE_TRIGGER_INVESTIGATION.md`）+ 本次确认。

| Workflow | 触发源 | Cron / 时间 | 兜底 | 状态 |
|---|---|---|---|---|
| **scan** | 外部（workflow_dispatch） | 北京 21:00（手工 / 外部触发） | **无** schedule | ⚠️ 缺 schedule（既有缺口） |
| **review** | GitHub schedule **+** 外部（dispatch） | `cron '23 22 * * 1-5'`（UTC 22:23 = 北京 Tue–Sat 06:23） | 无 | ⚠️ 双开待验证 |
| **dashboard-data** | GitHub schedule **+** push **+** dispatch | `*/15 * * * *`（每 15 分钟） | 无 | ✅ 正常 |
| **evolve** | GitHub schedule | 月频（每月 1 号） | — | ⚠️ 低频，注意 60 天暂停规则 |
| **news-fetch** | `needs: scan`（workflow_call） | —（由 scan 触发） | — | ✅ 链式 |
| **quant-research** | `needs: scan`（workflow_call） | —（由 scan 触发） | — | ✅ 链式 |

### 1.1 关键事实
- **scan 的 schedule 从没工作过 = 它根本不存在**（非失效）。这是"scan 多次手动触发"的根因。
- **review 的 schedule 配置合法**（cron 正确落在工作日），实际是否 fired 需 `gh` 查（私有仓无 token，本次无法列 run）。
- **dashboard-data 正常** = 它有 schedule + 仓库每日 push（60 天暂停规则不适用）。
- **news-fetch / quant-research** 是 `workflow_call`，由 scan 的 `jobs.scan` 通过 `needs` 调起，自身无独立 schedule。

---

## 2. 触发规则（设计原则）

### 2.1 三条基本原则

| 原则 | 适用 | 理由 |
|---|---|---|
| **时间敏感 → 外部触发**（cron-job.org / PAT） | scan（盘前 21:00 北京） | 需要"盘前固定时点"且**不被 GitHub 60 天暂停规则**影响；GitHub schedule 在私有仓低频时可能被 pause |
| **时间不敏感 → GitHub schedule** | review 复盘、dashboard 刷新、evolve 月频 | 频率高或低频，GitHub 原生 schedule 够用 |
| **链式 → `needs: scan`** | news-fetch、quant-research | 依赖 scan 的产物（CSV / AI 快照），必须等 scan 完成 |

### 2.2 为什么 scan 不该只靠 GitHub schedule
1. **60 天暂停规则**：仓库若 60 天无 push，所有 schedule 自动暂停。
   （本仓因 dashboard-data 每 15 分钟在跑，暂时不适用——但这是**脆弱依赖**。）
2. **cron 只认 UTC**：GitHub `cron` 字段**强制 UTC**，易写错时区（review 的 `22 23` 就是例子）。
3. **外部触发可审计**：cron-job.org 有执行日志、失败告警，比 GitHub 静默失败更易排查。

> 结论：**scan 用外部触发（cron-job.org）为主、GitHub dispatch 为兜底**；
> review / dashboard-data 维持 GitHub schedule（已工作）。

---

## 3. cron-job.org 模板（统一外部触发）

### 3.1 scan（北京 21:00 = UTC 13:00，冬令时；夏令时 UTC 12:00）

> ⚠️ 注意：北京 21:00 在冬令时 = UTC 13:00，夏令时 = UTC 12:00。
> cron-job.org 用 **UTC**，需按当前夏令时状态设。
> 推荐用 cron-job.org 的"时区"字段设为 `America/New_York` 再写 ET 时间，避免手工换算。

```
Job 名称: us-scan-nightly
URL:       https://api.github.com/repos/<owner>/<repo>/actions/workflows/scan.yml/dispatches
Method:    POST
Headers:   Content-Type: application/json
           Authorization: Bearer <PAT>
Body:      {"ref":"main"}
Schedule (cron-job.org 原生，设时区 America/New_York):
           0 21 * * 1-5      # 周一~周五 21:00 ET（盘前）
```

### 3.2 review（北京 06:23 = UTC 22:23 前一日，工作日）

```
Job 名称: us-review-nightly
URL:       https://api.github.com/repos/<owner>/<repo>/actions/workflows/review.yml/dispatches
Method:    POST
Headers:   Content-Type: application/json
           Authorization: Bearer <PAT>
Body:      {"ref":"main"}
Schedule:  23 22 * * 1-5     # UTC；或用 ET 时区写 06:23
```

> review **已**有 GitHub schedule（`22 23 * * 1-5` UTC）。外部触发是**冗余双保险**，
> 防 GitHub schedule 被 pause。注意：双开会产生重复 run，需在 workflow 内去重（见 §3.3）。

### 3.3 双开去重（若同时用 GitHub schedule + 外部触发）
- 方案 1：只保留一种（推荐 review 维持 GitHub，scan 用外部）。
- 方案 2：workflow 内加"最近 30 分钟已 run 则跳过"的 guard（需查 API，复杂）。
- **当前建议**：review 维持 GitHub schedule（已工作），**不**加外部触发 → 避免双开噪音。

---

## 4. 北京时间 ↔ UTC 换算表

> GitHub cron **强制 UTC**；cron-job.org 可设时区，但手动填 UTC 时按此表。

| 北京时间 | 冬令时（ET=UTC-5）UTC | 夏令时（ET=UTC-4）UTC | 星期 |
|---|---|---|---|
| 周一 21:00（scan 目标） | 周一 13:00 | 周一 12:00 | 1-5 |
| 周二 06:23（review） | 周一 22:23 | 周一 21:23 | 1-5（前一日） |
| 每 15 分钟 | 同北京 ±13/12h | 同北京 ±12/11h | 每天 |

> 美夏令时：3 月第二个周日 → 11 月第一个周日。
> 2026 夏令时结束：2026-11-01；12-06 及之后为**冬令时**（UTC = 北京 −13h）。

---

## 5. PAT 管理

### 5.1 一个 PAT 管所有
- 创建**单个** fine-grained PAT（或 classic `repo` scope），用于所有 cron-job.org 任务。
- 权限：`Actions: Read and Write`（触发 workflow_dispatch 需要 write）。
- 绑定到**单一仓库**（fine-grained 可限定 `<owner>/<repo>`），不授权其他仓。

### 5.2 泄露应急预案
| 步骤 | 动作 |
|---|---|
| 1 | **立即**在 GitHub Settings → Developer settings → PAT 处 **Revoke** 该 token |
| 2 | 在 cron-job.org 删除 / 暂停使用该 token 的所有 job |
| 3 | 检查近期 Actions run 历史，确认无异常 dispatch（尤其 scan / review 是否被恶意触发） |
| 4 | 重新生成新 PAT（相同 scope，换名便于追踪），更新 cron-job.org |
| 5 | 在 `WEEKEND_CHANGELOG.md` / 周报记录泄露事件与处置 |

> 建议：PAT 设**最短有效期**（如 1 年）+ 日历提醒续期；
> 不写进任何仓库文件（用 cron-job.org 的 secret 字段，不在 `.yml` 里）。

---

## 6. 与现有 flag 的协同

| flag | 触发相关 | 说明 |
|---|---|---|
| `ENABLE_SCAN_BUY_DECISION` | scan 的 `--buy-only` | flag 关 → scan 不接管买入，review 走旧路径 |
| `ENABLE_MACRO_PANEL` | scan 落 `macro_data.json` | flag 关 → 不落盘，前端不显示 |
| `ENABLE_TARGET_FILE` | scan 落 `portfolio_50000_target.csv` | 已激活（`"1"`） |

> 外部触发 scan 不改变 flag 行为——flag 仍由 repo variable 控制，周一 / 周二走旧路径不受影响。

---

## 7. 附：铁律确认
- 本文为只读汇总 + 设计文档，**仓库 `/tmp/us` 零改动**。
- 未运行任何会修改数据的 `.py`（仅只读 grep）。
- 未调用 AI。今晚 21:00 scan 与周二 06:23 review 不受影响。
