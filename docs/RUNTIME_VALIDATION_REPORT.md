# Runtime Validation Report

> 第二轮验证 · 只读 · 未修改任何文件
> 基准：`main @ 7724e03`
> 目标：确认当前 Runtime 状态设计能否满足"准确回答 Scan/Review/Evolve 运行状态"的需求

---

## 1. GitHub Actions API Available Fields

实测 `GET /repos/{repo}/actions/runs/{run_id}` 返回的**完整字段名**（scan run 36757957242）：

```
actor, artifacts_url, cancel_url, check_suite_id, check_suite_node_id,
check_suite_url, conclusion, created_at, display_title, event, head_branch,
head_commit, head_repository, head_sha, html_url, id, jobs_url, logs_url,
name, node_id, path, previous_attempt_url, pull_requests, referenced_workflows,
repository, rerun_url, run_attempt, run_number, run_started_at, status,
triggering_actor, updated_at, url, workflow_id, workflow_url
```

### API 实际存在的字段（与需求相关）

| 字段 | 含义 | 实测值（scan run）|
|---|---|---|
| `id` | run id | `36757957242` |
| `status` | 运行状态（queued / in_progress / completed 等）| `completed` |
| `conclusion` | 结论（success / failure / cancelled / skipped / neutral 等）| `success` |
| `created_at` | run 创建时间（schedule 触发时刻）| `2026-09-30T18:21:10Z` |
| `run_started_at` | run 实际开始执行时刻 | `2026-09-30T18:21:10Z` |
| `updated_at` | run 最后更新时间（近似完成时刻）| `2026-09-30T18:35:06Z` |
| `head_sha` | 完整 40 位 commit SHA | `9737418287b74bd0c422ec0d590a2a23bf2aea75` |
| `head_commit` | 完整 commit 对象（message/author 等）| 对象 |
| `event` | 触发事件（schedule / workflow_dispatch / push）| `schedule` |
| `workflow_id` | workflow 内部 id | `288956141` |
| `name` / `display_title` | workflow 名 | `美股盘中扫描` |
| `html_url` | run 网页链接 | 完整 URL |
| `run_attempt` | 重试次数 | `1` |
| `run_number` | 序号 | — |

### 关键结论：`completed_at` 不存在

**GitHub API 的 run 对象没有 `completed_at` 字段。** 结束时间只能由 `updated_at` 近似（在 completed 状态下，updated_at 即最后更新时间，通常等于完成时间）。

### 项目当前代码用到的字段 vs API 未用字段

**`fetch_runtimes.py:50-63` 只用 4 个字段**：`conclusion`（判 success）、`updated_at`（作 last_success_at）、`head_sha`（截 12 位）、`id`（作 run_id）。

**API 有但代码未用的字段**：`status`（判断 running 的关键！）、`created_at`、`run_started_at`、`event`、`html_url`、`workflow_id`、`head_commit`、`run_attempt`。

---

## 2. Current Runtime Schema

```json
"runtimes": {
  "scan":   {"last_success_at": "ISO UTC | null", "last_success_sha": "12位hex | null", "run_id": int|null},
  "review": {...},
  "evolve": {...}
}
```

来源：`fetch_runtimes.py:50`（`entry = {"last_success_at": None, "last_success_sha": None, "run_id": None}`）。

---

## 3. Can Current Schema Detect Running?

**不能。**

代码路径证明 —— `fetch_runtimes.py:31-35`：
```python
def _fetch(token, repo, workflow_file, timeout=30):
    url = (f".../actions/workflows/{workflow_file}/runs"
           f"?status=success&per_page=1")   # ← 只查询 status=success 的 run
```

- 查询条件 `status=success` 意味着**只返回已经成功的 run**。
- 正在运行的 run（`status=in_progress`）**不会被这个查询返回**。
- 因此当前 schema 中**不存在任何表示 running 的字段**，也无法从 `last_success_at` 推断出"当前正在运行"。

---

## 4. Can Current Schema Detect Failed?

**不能。**

同理：`status=success` 过滤掉了 `conclusion=failure` 的 run。若最近一次运行失败，fetch_runtimes 会**跳过失败 run、回退到更早的成功 run**。Dashboard 无从知道"最近一次运行失败了"。

---

## 5. Can Current Schema Detect Cancelled?

**不能。**

`conclusion=cancelled` 的 run 同样不在 `status=success` 结果里。当前 schema 无任何 cancelled 信息。

---

## 6. Current Dashboard Display Logic

### 完整链路（app.js）

```
boot()  (app.js:265)
  └─ window.fetch(dataUrl(), {cache:'no-store'})   (app.js:279)
       dataUrl() = DATA_URL + '?t=' + Date.now()   (app.js:21)
  └─ JSON.parse → 校验 d.stocks 数组
  └─ renderDashboard(d)  (app.js:328)
       └─ normalize(d): DATA = d  (app.js:148-149，runtimes 保留在 DATA 上)
       └─ renderRuntime()  (app.js:336, 396-413)
```

### renderRuntime 实际显示（app.js:396-413）

| 显示项 | 数据来源 | 缺失时显示 |
|---|---|---|
| SCAN / REVIEW / EVOLVE 标签 | 静态 DOM（index.html:31-45）| 恒显示 |
| 时间 | `entry.last_success_at` → `toBeijingTime()`（UTC+8）| `—`（NA = '—'，app.js:24）|
| SHA | `entry.last_success_sha` | 空字符串（`.rt-sha:empty{display:none}` 隐藏整行）|

### 不显示的内容（确认）

- ❌ 不显示 `run_id`
- ❌ 不显示 `status`
- ❌ 不显示 `conclusion`
- ❌ 不显示 `created_at`（只显示换算后的 last_success_at）
- ❌ 不显示原始 `updated_at`
- ✅ 显示 `SHA`（last_success_sha）

### fallback 行为

- `DATA.runtimes` 为 null/undefined → `var RT = DATA.runtimes || {}`，`RT.scan` 为 undefined → `entry && entry.last_success_at ? ... : NA` 显示 `—`。
- 单个 entry 字段为 null → 同样显示 `—` 或空。
- 页面**不会报错**（有判空保护），但会静默显示 N/A，无法区分"真的没数据" vs "API 失败"。

---

## 7. Dashboard Refresh / Staleness Analysis

### 时序（dashboard-data.yml）

```
GitHub Actions (dashboard-data.yml)
  ├─ schedule: */15 * * 1-5   （工作日每 15 分钟）
  ├─ workflow_dispatch
  └─ push (dashboard_export.py / summarize_run.py / dashboard-data.yml 变更时)
  ↓
Fetch workflow runtimes (fetch_runtimes.py → runtimes.json)
  ↓
Run dashboard_export.py (→ dashboard_data.json，含 runtimes)
  ↓
Summarize (→ last_run.json)
  ↓
Commit & push (→ origin/main)
  ↓
GitHub Pages 构建部署（max-age=600）
  ↓
前端 boot() fetch dashboard_data.json（页面加载时一次，无轮询）
```

### 结论

| 问题 | 答案 |
|---|---|
| Scan 正在运行时，dashboard-data 是否知道？| **否**。fetch_runtimes 只查 success，running run 不可见 |
| Dashboard 是否自动刷新？| **否**。boot() 只在页面加载 fetch 一次，无 setInterval/轮询；刷新需手动 F5 |
| Scan 失败，dashboard-data 是否仍运行？| **是**。dashboard-data 独立 schedule，与 scan 无关，照常每 15 分钟跑 |
| dashboard-data 在 Scan 之前执行，是否显示旧数据？| **是**。runtime 是"上一次 dashboard-data 运行时抓的快照"，天然滞后 |
| runtime 数据天然滞后？| **是**。最多滞后约 15 分钟（schedule 间隔）+ Pages 部署 10 分钟缓存 |

---

## 8. Workflow Schedule Analysis

### 当前 cron

| workflow | cron | 北京时间 | 状态 |
|---|---|---|---|
| scan | `7 13 * * 1-5` | 工作日 21:07 | ✅ 已改非整点 |
| review | `0 22 * * 1-5` | 工作日次日 06:00 | ⚠️ 整点 |
| evolve | `0 2 * * 6` | 周六 10:00 | ⚠️ 整点 |

### review 最近 schedule 为何是 01:10Z 而非 22:00Z

- review cron `0 22 * * 1-5` = 每天 22:00 UTC。
- 最近 schedule run `36799795650`：`created=10-01T01:10:15Z`，即 09-30 22:00 UTC 的调度**延迟约 3 小时 10 分钟**才触发。
- 与 scan 此前的 18:21Z（延迟 5h21m）同类：**GitHub 官方明示 schedule 在整点（start of every hour）高峰时段最易延迟/跳过**。
- 精确延迟时长不可控，无法从 API 反推"本应触发时刻"，标记为**待验证**（属 GitHub schedule 平台行为）。

### evolve 为何 09-05 后无 schedule run

- evolve 的 schedule 事件总数 = **0**（从未触发过）。
- evolve.yml 提交历史：`61de4fc`（09-29 22:34）才加入 schedule，`dd11d91`（09-30 08:35）改为 UTC `0 2 * * 6`。
- 09-05 至 09-29 之间 evolve.yml **没有 schedule**（靠人工 workflow_dispatch，而 09-05 后停止人工触发）。
- 09-29 加 schedule 后，第一个触发点应是**下个周六 10-04 02:00 UTC**（当前 10-01 尚未到达）。
- **结论：evolve 09-05 后无 run 是"schedule 刚加、首个周六未到"的正常现象，非 bug**（待 10-04 验证 schedule 是否真正触发）。

---

## 9. Confirmed Runtime Design Problems

| # | 问题 | 证据（文件:行）|
|---|---|---|
| 1 | **无法判断 running** | `fetch_runtimes.py:34` 只查 `status=success`，无 status 字段 |
| 2 | **无法判断 failed/cancelled** | 同上，failed/cancelled run 被过滤 |
| 3 | **无法判断"最近一次运行"成败** | 只能得到"最近一次成功"，非"最近一次运行" |
| 4 | **无法区分 latest vs last_success** | schema 只有 last_success_* 三个字段 |
| 5 | **run_id 写了但前端不显示** | `fetch_runtimes.py:60` 有 run_id，`app.js:396-413` 未读 |
| 6 | **无失败可观测性** | `fetch_runtimes.py:61-62` `except: pass` 静默 null |
| 7 | **Dashboard 无自动刷新** | `app.js:279` 仅页面加载 fetch 一次，无轮询 |
| 8 | **review/evolve 仍是整点 cron** | `review.yml` `0 22`、`evolve.yml` `0 2`（scan 已改 7 13）|

---

## 10. Problems That Are Only Cleanup（非功能缺陷）

| # | 项 | 说明 |
|---|---|---|
| 1 | `us-market-terminal/assets/*` | 旧前端 dead code（已 redirect）|
| 2 | `dashboard_export.py:2726-2732` mirror 写入 | dead write（无读者）|
| 3 | `dashboard_export.py:2402-2404` 默认 out_path | 指向已废弃目录 |
| 4 | `tencent_scf_review_trigger.py` | 已废弃 SCF 脚本 |

以上不影响 runtime 功能正确性，仅属清理项。

---

## 11. Recommended Runtime Schema

基于实际 GitHub API 字段与"要回答 9 个问题"的需求，建议**区分 latest 与 last_success**：

```json
"runtimes": {
  "scan": {
    "latest": {                       // 最近一次运行（无论成败/进行中）
      "run_id": 36757957242,
      "status": "completed",          // queued | in_progress | completed
      "conclusion": "success",        // success | failure | cancelled | skipped | null(运行中)
      "created_at": "2026-09-30T18:21:10Z",
      "started_at": "2026-09-30T18:21:10Z",   // 来自 run_started_at
      "updated_at": "2026-09-30T18:35:06Z",   // 结束时间近似（API 无 completed_at）
      "head_sha": "9737418287b7...",  // 完整或 12 位
      "event": "schedule",
      "html_url": "https://github.com/.../runs/36757957242"
    },
    "last_success": {                 // 最近一次成功运行
      "run_id": 36757957242,
      "completed_at": "2026-09-30T18:35:06Z", // 用 updated_at 近似
      "head_sha": "9737418287b7..."
    }
  },
  "review": {...},
  "evolve": {...}
}
```

### 关键设计依据（基于实际 API，非假设）

1. `status` 直接来自 API 的 `status` 字段（queued/in_progress/completed），可判断 running。
2. `conclusion` 来自 API `conclusion`，可判断 success/failure/cancelled。
3. **API 没有 completed_at**，结束时间用 `updated_at` 近似（并应改名为 `updated_at` 或注释说明，避免误以为有独立 completed_at）。
4. `latest` 需改查询条件：**去掉 `status=success` 过滤**（或改为 `per_page=1` 取最新一条，再单独再取 `status=success` 得 last_success）。
5. 前端渲染：`latest.status` 用于显示"运行中/失败/成功"，`last_success.*` 用于显示"最近成功时间/SHA"（保留现有"失败不覆盖成功时间"语义）。

### 实现改动范围（仅建议，未实施）

- `dashboard/fetch_runtimes.py`：改为每个 workflow 拉取 2 条（`per_page=1` 最新 + `status=success&per_page=1` 成功），组装 latest/last_success。
- `app.js renderRuntime()`：读 `latest.status/conclusion/head_sha` + `last_success.completed_at/head_sha`，增加 running/failed 视觉状态。
- 可选：前端加 `setInterval` 轮询（解决"不自动刷新"问题 #7）。

---

> 本次为只读验证，未修改任何代码/workflow/JSON，未 commit/push。所有不确定项（GitHub schedule 延迟精确时长、updated_at 是否严格等于完成时刻）已标注"待验证"。
