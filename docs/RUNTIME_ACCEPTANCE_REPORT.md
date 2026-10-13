# Runtime Acceptance Report

> 第四阶段：Runtime 实际部署前验收（只读，未改代码、未 commit/push）

---

## 1. Current dashboard_data.json Schema

**CURRENT_SCHEMA = old**

当前仓库 `dashboard/data/dashboard_data.json` 的 `runtimes` 仍是旧结构：
```
runtimes.scan.keys() = ['last_success_at', 'last_success_sha', 'run_id']
```

**原因（非缺陷）**：新代码（fetch_runtimes.py 输出 latest/last_success）尚未部署——未 commit/push，dashboard-data workflow 尚未用新 fetch_runtimes 重新生成 dashboard_data.json。这是"部署前"的预期过渡状态，**不应手工修改 JSON**，等部署后由 workflow 自然转换。

---

## 2. Local Dashboard Test

用修改后的 index.html / app.js / app.css + playwright 加载，7 个状态全部渲染正常、无 pageerror。

## 3. SUCCESS Test ✅
`status=completed, conclusion=success` → 显示 `SUCCESS` + `Last run: 2026-10-02 02:20:00` + `SHA abcdef123456 · Run #1234`

## 4. RUNNING Test ✅
`status=in_progress, conclusion=null` → 显示 `RUNNING` + `Started 2026-10-02 02:01:00`

## 5. FAILED Test ✅
`status=completed, conclusion=failure` → 显示 `FAILED` + `Last run: ...`

## 6. CANCELLED Test ✅
`status=completed, conclusion=cancelled` → 显示 `CANCELLED`

## 7. QUEUED Test ✅
`status=queued, conclusion=null` → 显示 `QUEUED` + `Queued ...`

## 8. SKIPPED Test ✅
`status=completed, conclusion=skipped` → 显示 `SKIPPED`

## 9. NO DATA Test ✅
`latest=null, last_success=null` → 显示 `NO DATA` + `—`（时间）+ 空 SHA（整行隐藏），不报错

---

## 10. Auto Refresh Test ✅

- `app.js:360`：`setInterval(refreshRuntime, 60000)` —— **60 秒**。
- `app.js:461-466`：`refreshRuntime()` 只执行 `window.fetch(dataUrl(), {cache:'no-store'})` → `DATA.runtimes = d.runtimes` → `renderRuntime()`。
- **不整页 reload**、不重置 stocks/market/options 等其他数据（只改 `DATA.runtimes`）。
- `dataUrl()`（app.js:20）加 `?t=Date.now()` cache-busting，避免浏览器缓存旧 runtime。

---

## 11. Real GitHub API Test ✅

实际运行 `dashboard/fetch_runtimes.py`（真实 token），scan/review/evolve 均得到：

| workflow | latest.status | latest.conclusion | last_success.run_id | error |
|---|---|---|---|---|
| scan | completed | success | 36757957242 | None |
| review | completed | success | 36799795650 | None |
| evolve | completed | success | 33937804241 | None |

三个 workflow 均正确输出 `latest` + `last_success` + `error`。

---

## 12. latest vs last_success Test ✅（本次改造最核心验收点）

构造「最新 = failure，更早 = success」：

```
latest.conclusion  = failure   (head_sha=badbadbadbad)
last_success.run_id = 9        (head_sha=goodgoodgood)
latest != last_success  = True
```

✅ 确认：最近一次运行失败时，`latest.conclusion=failure`，而 `last_success` 仍保留之前最近一次成功运行 —— **latest 与 last_success 正确分离**，不再因为"失败"而丢失"最近成功"。

---

## 13. dashboard_export Test ✅

`dashboard_export.py`：
- `line 2629`：`runtimes = json.loads(rt_path.read_text())`（读 fetch_runtimes 输出）
- `line 2644`：`payload["runtimes"] = runtimes`（**直接透传**）

确认**没有**把新 schema 转回旧 schema：`fetch_runtimes → dashboard_export → dashboard_data.json` 结构完全一致（latest/last_success/error 原样保留）。

---

## 14. Final Result

# PASS ✅

- 7 个状态（SUCCESS/RUNNING/FAILED/CANCELLED/QUEUED/SKIPPED/NO DATA）渲染全部正确，无 pageerror。
- 60 秒自动刷新：只更新 `DATA.runtimes`，不整页 reload、不破坏其他数据、带 cache-busting。
- 真实 GitHub API：scan/review/evolve 均得到 latest/last_success/error。
- **latest vs last_success 核心逻辑验证通过**（failure 最新时 latest≠last_success）。
- dashboard_export 纯透传，结构不退化。

**唯一备注（非 FAIL）**：当前仓库 `dashboard_data.json` 仍是 old schema，因为新代码尚未部署（未 commit/push）。部署并让 dashboard-data workflow 用新 fetch_runtimes 运行一次后，dashboard_data.json 会自然转为 latest/last_success 结构。

> 本次验收全程只读，未修改 Runtime/scan/review/evolve/schedule，未删旧架构，未 commit/push。
