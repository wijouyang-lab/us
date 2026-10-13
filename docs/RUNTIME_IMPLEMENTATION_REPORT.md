# Runtime Implementation Report

> 第三阶段：Runtime 架构改造（last_success only → latest + last_success）
> 未 commit / 未 push · 未改 schedule · 未改核心业务逻辑 · 未删除旧架构

---

## 1. Modified Files

| 文件 | 改动 |
|---|---|
| `dashboard/fetch_runtimes.py` | 核心改造：取消 `status=success` 过滤，输出 `latest` + `last_success` + `error` |
| `app.js` | 重写 `renderRuntime()`（读 latest/last_success，状态徽章）+ 新增 `refreshRuntime()` + 60 秒自动刷新 |
| `index.html` | runtime-strip 每项新增状态徽章 DOM（`scanStatus`/`reviewStatus`/`evolveStatus`）|
| `app.css` | 新增 `.rt-status` 状态徽章样式（running/queued/success/failed/cancelled/skipped/nodata）|
| `tests/test_dashboard_runtime.py` | 更新为新 schema 测试（19 项）|

**`dashboard_export.py` 未改动** —— 它是 runtimes 的纯透传层（`line 2623-2634` 读 runtimes.json、`line 2644` 组装进 payload），新结构自动生效，无需修改。

---

## 2. Runtime Schema Before

```json
"runtimes": {
  "scan":   {"last_success_at": "ISO|null", "last_success_sha": "12位hex|null", "run_id": int|null},
  "review": {...},
  "evolve": {...}
}
```

## 3. Runtime Schema After

```json
"runtimes": {
  "scan": {
    "latest": {
      "run_id": 123,
      "status": "completed",          // queued | in_progress | completed
      "conclusion": "success",        // success | failure | cancelled | skipped | null(运行中)
      "created_at": "2026-09-30T18:21:10Z",
      "started_at": "2026-09-30T18:21:10Z",   // 来自 run_started_at
      "updated_at": "2026-09-30T18:35:06Z",
      "head_sha": "9737418287b7",             // 前 12 位
      "event": "schedule",
      "run_number": 148,
      "run_attempt": 1,
      "html_url": "https://github.com/.../runs/123"
    },
    "last_success": {
      "run_id": 123,
      "completed_at": "2026-09-30T18:35:06Z",  // = updated_at（API 无 completed_at）
      "head_sha": "9737418287b7"
    },
    "error": null
  },
  "review": {...}, "evolve": {...}
}
```

---

## 4. fetch_runtimes.py Changes

1. **取消过滤**：`?status=success&per_page=1` → `?per_page=10`（fetch 最近 10 条，running/failed/cancelled 均可见）。
2. **latest**：`runs[0]`（GitHub API 默认按 created_at 倒序）→ `_build_latest()` 映射为 latest 结构，**原样保留 `status` 与 `conclusion`**。
3. **last_success**：遍历 runs，取第一条 `conclusion == "success"` 的记录。
4. **completed_at 注释**：`last_success.completed_at` 用 `updated_at`，并注明 `GitHub Actions API does not expose completed_at; updated_at is used as the completion-time approximation.`
5. **新增 `_short_sha()` / `_build_latest()`** 辅助函数。

---

## 5. dashboard_export.py Changes

**无改动。** 理由：现有代码 `line 2623-2634` 用 `json.loads(rt_path.read_text())` 读取 runtimes.json 并直接赋值给 `payload["runtimes"]`（line 2644），是纯透传。新结构由 fetch_runtimes.py 保证；runtimes 文件缺失/读取失败时 `runtimes = None`，前端 `DATA.runtimes || {}` 兜底显示 NO DATA，不会报错。

---

## 6. app.js Changes

1. **`renderRuntime()` 重写**：从读 `last_success_at/last_success_sha` 改为读 `latest` + `last_success`，按 `latest.status` / `latest.conclusion` 渲染状态徽章与时间文案：
   - `in_progress` → `RUNNING` + `Started <started_at>`
   - `queued/pending/waiting/requested` → `QUEUED` + `Queued <created_at>`
   - `completed + success` → `SUCCESS` + `Last run: <updated_at>`
   - `completed + failure` → `FAILED`
   - `completed + cancelled` → `CANCELLED`
   - `completed + skipped` → `SKIPPED`
   - 无 latest → `NO DATA`
   - SHA 显示 `latest.head_sha`（fallback `last_success.head_sha`）+ `Run #<run_number>`
2. **`toBeijingTime()`**：保留（UTC+8 固定转换）。
3. **`normalize()`**：保留（`DATA = data`，runtimes 原样保留）。

---

## 7. Auto Refresh Changes

新增 `refreshRuntime()`（app.js）：
- 每 60 秒 `setInterval(refreshRuntime, 60000)`（在 `renderDashboard` 末尾用 `window.__runtimeTimer` 防重复启动）。
- 只重新 `fetch(dataUrl(), {cache:'no-store'})` 并**只更新 `DATA.runtimes` + 重跑 `renderRuntime()`**，不整页 reload、不触碰其他页面状态（stocks/market/options 等不变）。
- `dataUrl()` 已带 `?t=Date.now()` cache-busting（原有逻辑保留）。

---

## 8. Error Handling Changes

`fetch_runtimes.py` 的 `except: pass` 已删除，改为：
```python
except Exception as e:
    entry["error"] = {"type": type(e).__name__, "message": str(e)}
```
- 单个 workflow API 失败 → 该 workflow 的 `latest`/`last_success` 置 null，`error` 记录异常类型与消息。
- **不崩溃**：scan 失败不影响 review/evolve 正常输出（已验证）。

---

## 9. Tests Performed

| Test | 内容 | 结果 |
|---|---|---|
| Test 1 | 实际 API 拉取 scan/review/evolve 得 latest+last_success | ✅ 通过 |
| Test 2 | completed+success → latest.status=completed, conclusion=success | ✅ 通过 |
| Test 3 | running → latest.status=in_progress, conclusion=null（+ last_success 为更早 success）| ✅ 通过 |
| Test 4 | failed/cancelled/skipped 不被过滤，last_success 回退更早 success | ✅ 通过 |
| Test 5 | dashboard_export 透传新结构（scan/review/evolve 各有 latest/last_success/error）| ✅ 通过 |
| Test 6 | 前端 renderRuntime 各状态渲染（playwright mock，running/success/failed/queued/cancelled/skipped/nodata）不崩溃 | ✅ 通过 |
| Test 7 | cache-busting（dataUrl `?t=` + cache no-store）| ✅ 通过 |
| Test 8 | py_compile + node --check + git diff --check + 全量测试 | ✅ 通过 |

---

## 10. Test Results（全量）

| 测试 | 结果 |
|---|---|
| test_dashboard_runtime（更新后）| **19/19** ✅ |
| test_milestone_win_rate | 16/16 ✅ |
| test_event_key_p2 | 15/15 ✅ |
| test_p3_data_quality | 16/16 ✅ |
| test_p3_5_rec_price_repair | 12/12 ✅ |
| test_p05_repair_regression | 45/45 ✅ |
| test_milestone_backfill | 20/20 ✅ |
| test_backfill_integration | 10/10 ✅ |
| test_rec_price_failclosed | 15/15 ✅ |
| test_stop_loss_safety | 27/27 ✅ |
| test_stop_loss_sanity | 23/23 ✅ |
| py_compile（fetch_runtimes/summarize_run/dashboard_export/scan/review）| ✅ |
| node --check app.js | ✅ |
| git diff --check | ✅ |

---

## 11. Remaining Issues

1. **旧数据兼容**：`dashboard/data/dashboard_data.json` 当前仍是旧格式（last_success_at），需等下一次 dashboard-data workflow 运行（fetch_runtimes 输出新结构 + dashboard_export 透传）才会变成 latest/last_success。此前前端 renderRuntime 对旧格式会显示 NO DATA（latest 为 undefined），属预期过渡行为。
2. **`run_id` / `html_url` 前端仍未展示**：latest 结构已含 run_id、html_url、event、run_attempt，但 UI 目前只展示 status/conclusion/时间/SHA/Run#。可后续按需加链接。
3. **schedule 问题未处理**（按用户要求分开）：review `0 22`、evolve `0 2` 仍是整点 cron，待单独处理。
4. **旧架构未清理**（按用户要求分开）：us-market-terminal/assets、mirror write、tencent_scf_review_trigger.py 等。

---

## 12. Git Diff Summary

```
 app.css                         |  10 ++-
 app.js                          |  80 ++++++++++++++----
 dashboard/fetch_runtimes.py     |  90 ++++++++++++++++------
 index.html                      |  11 ++--
 tests/test_dashboard_runtime.py | 142 +++++++++++++++++-------------
 5 files changed, 240 insertions(+), 93 deletions(-)
```

- `git diff --check`：无空白错误。
- `git status`：仅 5 个文件修改（app.css / app.js / dashboard/fetch_runtimes.py / index.html / tests/test_dashboard_runtime.py），无数据文件改动。
- **未 commit、未 push**。
