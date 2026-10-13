# Project Audit Report

> 只读审计 · 未修改任何文件 · 未 commit/push · 未运行会修改数据的命令
> 审计基准：`main @ 7724e03`（fix: move scan schedule off the hour）

---

## 1. Architecture

### 目录树（关键文件）

```
/ (repo root)
├── index.html                  # Dashboard 唯一正式前端入口（含 runtime-strip DOM）
├── app.js                      # 前端逻辑（renderRuntime / normalize / renderHeader 等）
├── app.css                     # 前端样式（.runtime-strip / .rt-*）
├── dashboard_export.py         # 数据生成主脚本（读取 CSV → 组装 dashboard_data.json）
├── dashboard/
│   ├── fetch_runtimes.py       # 【新增】从 GitHub API 读 scan/review/evolve 最近成功 run
│   ├── summarize_run.py        # 把 dashboard_data.json 抽成 last_run.json 摘要
│   └── data/
│       ├── dashboard_data.json # 前端唯一数据源（含 runtimes 字段）
│       ├── last_run.json       # 运行摘要（含 runtimes 副本）
│       └── last_run.log        # 最近一次 dashboard_export 运行日志
├── scan.py                     # 美股盘中扫描（选股/AI/止损/期权，与 runtime 无关）
├── review.py                   # 美股盘后复盘（止损/milestone/胜率）
├── evolve.py                   # 策略进化（月度）
├── scan_us_option_engine.py    # 期权策略引擎（SHORT_PUT / CALL_DEBIT_SPREAD）
├── option_strategies.csv       # 期权策略账本
├── trade_history.csv           # 股票交易账本
├── review_history.csv          # 复盘历史（event key / milestone / PnL）
├── ai_snapshot.csv             # AI 快照（按 Ticker|Rec_Date|Tag）
├── ai_text_cache.csv           # AI 文本缓存
├── us_stocks_pending_*.csv.processed  # 每日 pending 名单
├── tencent_scf_review_trigger.py      # 【已废弃】Review SCF 触发器（review 已迁移到 schedule）
├── us-market-terminal/         # 【旧前端，已废弃】index.html 已改为 redirect
│   ├── index.html              # redirect 页面（meta refresh + location.replace('../')）
│   ├── assets/app.js           # 【dead code】旧前端 JS
│   ├── assets/app.css          # 【dead code】旧前端 CSS
│   └── dashboard/data/dashboard_data.json  # 【dead write】mirror 数据（前端不再读取）
├── .github/workflows/
│   ├── scan.yml                # Scan 调度（workflow_dispatch + cron '7 13 * * 1-5'）
│   ├── review.yml              # Review 调度（cron '0 22 * * 1-5'）
│   ├── evolve.yml              # Evolve 调度（cron '0 2 * * 6'）
│   └── dashboard-data.yml      # Dashboard 数据刷新（schedule */15 + workflow_dispatch + push）
└── tests/
    ├── test_dashboard_runtime.py        # runtime metadata 测试（11 项）
    ├── test_milestone_win_rate.py       # P1 胜率测试
    ├── test_event_key_p2.py             # P2 event key 测试
    ├── test_p3_data_quality.py          # P3 数据质量测试
    ├── test_p3_5_rec_price_repair.py    # P3.5 Rec_Price 修复测试
    └── test_p05_repair_regression.py    # P0.5 Stop_Loss 修复回归测试
```

### 关键文件职责

| 文件 | 职责 |
|---|---|
| `dashboard/fetch_runtimes.py` | 只读调用 GitHub API，取 scan/review/evolve 最近一次 **success** run 的 `updated_at`/`head_sha`/`id`，输出 JSON 到 stdout |
| `dashboard_export.py` | 读 pending CSV + trade_history + option_strategies + review_history，组装含 `runtimes` 字段的 `dashboard_data.json`，并 mirror 到 us-market-terminal |
| `dashboard/summarize_run.py` | 抽 `dashboard_data.json` 关键指标成 `last_run.json`，并把 `runtimes` 原样并入 |
| `app.js` | `renderRuntime()` 读 `DATA.runtimes` 渲染顶部 SCAN/REVIEW/EVOLVE 卡片 |
| `index.html` | `#runtimeStrip` DOM 骨架 + 顶部 header |
| `.github/workflows/dashboard-data.yml` | 编排：fetch_runtimes → dashboard_export → summarize → validate → commit |

---

## 2. Git State

| 项 | 值 |
|---|---|
| branch | `main` |
| HEAD | `7724e03da7de41c73936a77f15132733e55e02f3` |
| git status | clean（无未提交修改）|

最近 10 个 commit：
```
7724e03 fix: move scan schedule off the hour
e020fe2 chore(dashboard): refresh market data [skip ci]
4b7f185 chore(dashboard): refresh market data [skip ci]
771cb11 chore(dashboard): refresh market data [skip ci]
7a742d7 chore(dashboard): refresh market data [skip ci]
2604a87 chore(dashboard): refresh market data [skip ci]
7fbd68d chore(dashboard): refresh market data [skip ci]
6079da7 chore(dashboard): refresh market data [skip ci]
dd20302 chore(dashboard): refresh market data [skip ci]
4b95729 chore(dashboard): refresh market data [skip ci]
```

最近一次 commit（7724e03）涉及文件：仅 `.github/workflows/scan.yml`（+1/-1，cron `0 13` → `7 13`）。

无未提交修改。

---

## 3. Recent Changes（Runtime Metadata 改造）

### 已修改文件

| 文件 | 改动 | 状态 |
|---|---|---|
| `dashboard/fetch_runtimes.py` | 新增：从 GitHub API 读最近成功 run | ✅ 完成 |
| `dashboard_export.py` | 新增 `--runtimes` 参数 + payload `runtimes` 字段（line 2391-2393, 2623-2634, 2644）| ✅ 完成 |
| `dashboard/summarize_run.py` | `runtimes: d.get("runtimes")` 并入 last_run.json（line 68）| ✅ 完成 |
| `.github/workflows/dashboard-data.yml` | `actions: read` 权限 + Fetch workflow runtimes step + `--runtimes` 传参 | ✅ 完成 |
| `index.html` | 顶部新增 `#runtimeStrip` 三块 DOM + `app.css/app.js?v=runtime1` cache-busting | ✅ 完成 |
| `app.css` | `.runtime-strip` / `.rt-*` 样式 + `::before` 前缀 | ✅ 完成 |
| `app.js` | `toBeijingTime()` + `renderRuntime()`（读 `DATA.runtimes`）| ✅ 完成 |
| `us-market-terminal/index.html` | 旧入口改为 redirect 到 `../` | ✅ 完成 |
| `tests/test_dashboard_runtime.py` | 新增 11 项 runtime 测试 | ✅ 完成 |

### 部分完成 / 仍依赖旧逻辑 / 新旧并存

1. **`us-market-terminal/` 旧架构未清理（新旧并存）**：
   - `dashboard_export.py` line 2726-2732 仍在把数据 **mirror 写入** `us-market-terminal/dashboard/data/dashboard_data.json`，但该目录前端 index.html 已 redirect，无读者 → **dead write**。
   - `dashboard_export.py` line 2402-2404 的默认 `out_path` 仍**优先指向** `us-market-terminal/dashboard/data/`（仅当未显式传 `--out` 时；workflow 显式传了 `--out dashboard/data/dashboard_data.json` 所以未触发该分支）。
   - `us-market-terminal/assets/app.js`、`assets/app.css` 是旧前端资源，已无引用 → **dead code**。
   - `tencent_scf_review_trigger.py`：Review 的 SCF 触发器，Review 已迁移到 schedule → **已废弃但未删除**。

2. **`runtimes.json` 是临时文件**：workflow 中 `python dashboard/fetch_runtimes.py > dashboard/data/runtimes.json` 生成，但不进 git（commit 步骤只 add dashboard_data.json/last_run.json/last_run.log）。

3. **review.yml / evolve.yml 的 schedule 仍是整点 cron**（`0 22`、`0 2`），scan 已改为 `7 13` 避开整点，但 review/evolve 尚未同步调整（见 bug #7）。

---

## 4. Runtime Data Flow（任务启动 → 网页显示）

```
GitHub Actions (dashboard-data.yml 定时/schedule 或 workflow_dispatch)
  │
  ├─ Step "Fetch workflow runtimes"
  │     python dashboard/fetch_runtimes.py > dashboard/data/runtimes.json
  │     └─ fetch_runtimes() 函数 (fetch_runtimes.py:46-64)
  │        └─ _fetch() 调 GitHub API:
  │           GET /repos/{repo}/actions/workflows/{scan|review|evolve}.yml/runs?status=success&per_page=1
  │           → 取 runs[0] 的 updated_at / head_sha[:12] / id
  │           → 输出 {scan:{last_success_at,last_success_sha,run_id}, review:{...}, evolve:{...}}
  │
  ├─ Step "Run dashboard_export.py"
  │     python dashboard_export.py --runtimes dashboard/data/runtimes.json ...
  │     └─ line 2623-2634 读 runtimes.json → runtimes 变量
  │     └─ line 2637-2644 组装 payload，其中 "runtimes": runtimes
  │     └─ line 2723-2732 写 dashboard/data/dashboard_data.json（+ mirror 到 us-market-terminal）
  │
  ├─ Step "Summarize run"
  │     python dashboard/summarize_run.py ... 
  │     └─ line 68: "runtimes": d.get("runtimes") → 并入 last_run.json
  │
  └─ Step "Commit and push if changed"（push 到 origin/main）
        │
        ▼
GitHub Pages（source = main 根目录）构建部署
        │
        ▼
前端 index.html + app.js
  │
  ├─ boot() → fetch('dashboard/data/dashboard_data.json?t='+Date.now(), {cache:'no-store'})
  │           (app.js:16, 21, 279)
  ├─ renderDashboard(data) (app.js:328)
  │     └─ normalize(data) → DATA = data  (app.js:148-149，runtimes 字段被保留在 DATA 上)
  │     └─ renderRuntime() (app.js:336, 396-413)
  │           └─ 读 DATA.runtimes.scan/review/evolve
  │              ├─ 时间: toBeijingTime(entry.last_success_at)  (app.js:385-394, UTC+8 固定)
  │              └─ SHA : entry.last_success_sha → 写入 #scanRunSha 等
  │     └─ DOM 写入 #scanRunTime / #scanRunSha / #reviewRunTime / ... / #evolveRunSha
```

---

## 5. Runtime Metadata Schema（代码中真实存在的字段）

实际 schema **只有 3 个字段**（`fetch_runtimes.py:50-63`、`app.js:402-407`）：

```json
"runtimes": {
  "scan":   {"last_success_at": "ISO8601 UTC 字符串或 null",
             "last_success_sha": "12 位 hex 或 null",
             "run_id": 整数或 null},
  "review": { ...同上... },
  "evolve": { ...同上... }
}
```

**不存在的字段**（用户问题里假设的 schema 均未在代码中出现，已确认）：
`status`、`started_at`、`completed_at`、`current_stage`、`progress`、`message`、`error`、`model` —— **全部不存在**。

语义说明：
- `last_success_at` = 该 workflow **最近一次 success run** 的 `updated_at`（fetch_runtimes.py:57，注释声明用 updated_at 作为完成时间）。
- `last_success_sha` = 该 run 的 `head_sha[:12]`。
- `run_id` = 该 run 的 `id`（后端写入，前端**未显示**）。

---

## 6. Dashboard Data Flow（字段一致性）

### 前端期待字段（app.js:396-413）
```
DATA.runtimes.scan.last_success_at   → #scanRunTime
DATA.runtimes.scan.last_success_sha  → #scanRunSha
DATA.runtimes.review.last_success_at / last_success_sha
DATA.runtimes.evolve.last_success_at / last_success_sha
```

### 后端实际提供字段（fetch_runtimes.py:50-63）
```
runtimes.scan.last_success_at / last_success_sha / run_id
runtimes.review.last_success_at / last_success_sha / run_id
runtimes.evolve.last_success_at / last_success_sha / run_id
```

### 一致性结论
- `last_success_at` / `last_success_sha`：**名称一致、类型一致**（均为 string|null）。
- `run_id`：后端提供，前端未读取（非 bug，仅未展示）。
- 无「后端改了字段但前端读旧字段」问题（当前两端字段一致）。
- **null 处理**：API 失败时字段为 null（fetch_runtimes.py:61-62 `except: pass`），前端 `entry && entry.last_success_at ? ... : NA` 显示 `—`，SHA 显示空（`.rt-sha:empty{display:none}`）。null 不会报错，但会静默显示 N/A，无从诊断原因。

### 旧数据 / stale 风险
- 前端 fetch 带 `?t=Date.now()` 且 `cache:'no-store'`（app.js:21, 279）→ JSON 不缓存。
- 但 `index.html` 本身引用 `app.js?v=runtime1`、`app.css?v=runtime1`（cache-busting 已加），index.html 自身由 GitHub Pages 返回 `Cache-Control: max-age=600`（10 分钟），仍有最多 10 分钟旧 HTML 风险（此前双入口问题已通过 redirect 解决）。

---

## 7. Confirmed Bugs

| # | 类别 | 文件:行 | 说明 |
|---|---|---|---|
| 1 | L dead code / duplicate | `us-market-terminal/assets/app.js`、`assets/app.css` | 旧前端资源，前端已 redirect，无引用 |
| 2 | L dead write | `dashboard_export.py:2726-2732` | 仍 mirror 数据到 `us-market-terminal/dashboard/data/`，但无读者 |
| 3 | L dead config | `dashboard_export.py:2402-2404` | 默认 `out_path` 仍优先指向已废弃的 us-market-terminal 目录（workflow 显式 `--out` 规避，但裸跑会写错位置）|
| 4 | L dead code | `tencent_scf_review_trigger.py` | Review 已迁到 schedule，此 SCF 触发器已废弃未删 |
| 5 | M 异常吞掉 | `dashboard/fetch_runtimes.py:61-62` | `except Exception: pass`，GitHub API 失败时静默 null，无 error 字段可诊断 |

## 8. Suspected Bugs（待验证）

| # | 类别 | 位置 | 说明 | 证据 |
|---|---|---|---|---|
| 6 | F run_id/commit 语义 | `fetch_runtimes.py:57` | `last_success_at` 用 `updated_at` 而非独立 `completed_at`（GitHub run 对象本就没有 completed_at），updated_at 在 run 完成后仍可能被更新（rerun 等）→ 时间可能不是严格"完成时刻" | 待验证 updated_at 是否等于完成时间 |
| 7 | J workflow 与 Dashboard 状态不一致 | `review.yml` cron `0 22`、`evolve.yml` cron `0 2` | scan 已改 `7 13` 避开整点，但 review/evolve 仍是整点 cron，同样会遭遇整点高峰延迟（与 scan 此前同因）| review 最近 schedule run 实际在 `10-01T01:10:15Z`（预期 09-30 22:00 UTC，延迟约 3h10m）；evolve schedule 从未触发过（event=schedule total=0）|
| 8 | D/E runtime 不实时 / 无状态 | 整体架构 | runtime 只记录"最近成功时间"，**不追踪"当前运行中/失败"状态** → Dashboard 无法显示 running/failed 状态，失败只能从"时间没更新"间接推断 | 无 status/progress 字段（见 §5）|
| 9 | B 数据写入未读取 | `fetch_runtimes.py:60` vs `app.js` | `run_id` 后端写入但前端不显示（非致命，属未使用字段）| — |

---

## 9. Missing Information（待验证）

1. `fetch_runtimes.py` 用 `updated_at` 作为 `last_success_at` 的精确语义 —— 需确认 GitHub run 的 `updated_at` 是否严格等于"成功完成时刻"（GitHub API 无独立 completed_at 字段）。
2. review.yml / evolve.yml 的 schedule 触发延迟是"整点高峰延迟"还是"连续改 cron 后注册不稳定"—— 与 scan 此前同类问题，需观察后续整点 vs 非整点的稳定触发情况。
3. `us-market-terminal/assets/` 与 `tencent_scf_review_trigger.py` 是否可安全删除 —— 需确认无其他隐藏引用（本次 grep 未发现，但未做全量依赖分析）。

---

## 10. Relevant Files（最重要的 5 个）

1. **`dashboard_export.py`** —— 数据组装主脚本，产出 dashboard_data.json（含 runtimes 字段、mirror 逻辑）。
2. **`dashboard/fetch_runtimes.py`** —— runtime metadata 唯一数据源（从 GitHub API 读最近成功 run）。
3. **`app.js`** —— 前端核心，`renderRuntime()` / `normalize()` / `toBeijingTime()` 负责读取并渲染 runtime。
4. **`.github/workflows/dashboard-data.yml`** —— 编排 runtime 采集与数据刷新。
5. **`index.html`** —— 前端入口与 `#runtimeStrip` DOM 骨架。

---

## 11. Relevant Code Snippets

### runtime 写入（读取 GitHub API）
```python
# dashboard/fetch_runtimes.py:46-64
def fetch_runtimes(token, repo):
    out = {}
    for key, wf in WORKFLOWS.items():
        entry = {"last_success_at": None, "last_success_sha": None, "run_id": None}
        try:
            data = _fetch(token, repo, wf)          # .../runs?status=success&per_page=1
            runs = data.get("workflow_runs") or []
            if runs:
                r = runs[0]
                if r.get("conclusion") == "success":
                    entry["last_success_at"] = r.get("updated_at") or r.get("created_at")
                    sha = r.get("head_sha") or ""
                    entry["last_success_sha"] = sha[:12] if sha else None
                    entry["run_id"] = r.get("id")
        except Exception:
            pass                                   # ← 异常被吞（bug #5）
        out[key] = entry
    return out
```

### runtime 组装进 payload
```python
# dashboard_export.py:2623-2644
runtimes = None
if args.runtimes:
    rt_path = Path(args.runtimes)
    if rt_path.exists():
        try:
            runtimes = json.loads(rt_path.read_text(encoding="utf-8"))
        except Exception as e:
            log(f"[WARN] 读取 runtimes 失败（{e}），runtimes 置 null")
payload = {
    "generated_at": ...,
    "stocks": ..., "market": ..., "options": ...,
    "review": ..., "history": ...,
    "runtimes": runtimes,                          # ← 顶层 runtimes 字段
    "meta": {...},
}
```

### 前端读取 + 渲染
```js
// app.js:396-413
function renderRuntime() {
  var RT = DATA.runtimes || {};
  function fill(timeId, shaId, entry) {
    var timeEl = $('#' + timeId), shaEl = $('#' + shaId);
    if (timeEl) {
      timeEl.textContent = (entry && entry.last_success_at) ? toBeijingTime(entry.last_success_at) : NA;
      timeEl.title = 'Last Successful Run · Asia/Shanghai (UTC+8) · 失败/取消的运行不会覆盖此时间';
    }
    if (shaEl) shaEl.textContent = (entry && entry.last_success_sha) ? entry.last_success_sha : '';
  }
  fill('scanRunTime', 'scanRunSha', RT.scan);
  fill('reviewRunTime', 'reviewRunSha', RT.review);
  fill('evolveRunTime', 'evolveRunSha', RT.evolve);
}
```

### workflow 编排
```yaml
# .github/workflows/dashboard-data.yml:69-94
- name: Fetch workflow runtimes
  run: python dashboard/fetch_runtimes.py > dashboard/data/runtimes.json
- name: Run dashboard_export.py
  run: python dashboard_export.py ... --runtimes dashboard/data/runtimes.json
- name: Summarize run
  run: python dashboard/summarize_run.py dashboard/data/dashboard_data.json dashboard/data/last_run.json
```

---

## 12. Recommended Fix Order

1. **（低风险）删除 dead code / dead write**：`us-market-terminal/assets/`、`tencent_scf_review_trigger.py`、以及 `dashboard_export.py` 的 mirror 逻辑（2726-2732）和默认 out_path 指向 us-market-terminal 的分支（2402-2404）。前置：确认无其他引用。
2. **（低风险）异常可观测**：`fetch_runtimes.py` 的 `except: pass` 改为记录一个 `"error"` 字段（如 `{"last_success_at":null, "error":"HTTP 403"}`），让 API 失败可诊断（对应 bug #5、§5 缺失 error 字段）。
3. **（中风险）review/evolve schedule 避开整点**：仿照 scan 的 `7 13`，把 review `0 22` → 非整点（如 `7 22`）、evolve `0 2` → 非整点，规避整点高峰延迟（对应 bug #7）。**需用户确认**，本次审计不实施。
4. **（可选）展示 run_id**：前端 renderRuntime 增加 run_id 展示，消除"后端写了前端不读"（bug #9）。
5. **（可选）runtime 状态化**：若需要"运行中/失败"实时状态，需新增 status/progress 字段并在 fetch_runtimes 中按 `status`（非仅 success）拉取 —— 属架构扩展，非当前缺陷。

> 本次为只读审计，以上均为建议，未实施任何修改。
