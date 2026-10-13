# Runtime Collector 触发修复 — 报告

> 独立小修复：让 `dashboard-data.yml` 在 `dashboard/fetch_runtimes.py` 变更时自动触发
> 日期：2026-10-02（GMT+8）

---

## 1. 修改文件

| 项目 | 值 |
| --- | --- |
| 修改文件 | `.github/workflows/dashboard-data.yml`（唯一） |
| 修改位置 | `on.push.paths` |
| 修改性质 | 仅**新增**一行 path，保留原有全部 paths |

### diff

```diff
@@ -27,6 +27,7 @@ on:
   push:
     paths:
       - dashboard_export.py
+      - dashboard/fetch_runtimes.py
       - dashboard/summarize_run.py
       - .github/workflows/dashboard-data.yml
```

> `git diff --check` 无空白错误；`git status` 确认**仅**该 workflow 文件被修改，未触碰 Runtime 代码、Dashboard 前端、数据文件或其他 workflow，无任何删除。

### 修改后 push.paths 完整清单（4 项）

1. `dashboard_export.py`（保留）
2. `dashboard/fetch_runtimes.py`（**新增**）
3. `dashboard/summarize_run.py`（保留）
4. `.github/workflows/dashboard-data.yml`（保留）

> schedule（`*/15 * * * 1-5`）与 `workflow_dispatch` 均未改动。

---

## 2. Commit

| 项目 | 值 |
| --- | --- |
| Commit SHA | `5d65f8447fe2fc002c4dc49a34a688e5db4d3dce`（短 `5d65f84`） |
| Message | `fix(workflow): refresh dashboard when runtime collector changes` |
| 变更规模 | 1 file changed, 1 insertion(+) |

---

## 3. Push

| 项目 | 结果 |
| --- | --- |
| Push 结果 | ✅ 成功 |
| Push 范围 | `1eba873..5d65f84  main -> main` |
| 方式 | rebase 到远端最新后 fast-forward，无 force push |

---

## 4. Workflow 自动触发验证

| 项目 | 值 |
| --- | --- |
| 触发方式 | ✅ **自动触发**（`event=push`） |
| Run ID | `36905057177` |
| Status | `completed` |
| Conclusion | ✅ `success` |
| head_sha | `5d65f844`（本次 push 的 commit） |
| Run URL | https://github.com/wijouyang-lab/us/actions/runs/36905057177 |

> 关键确认：该 run 的 `event` 为 `push`（而非 `workflow_dispatch`），证明 `dashboard-data.yml` 因本次 push 修改 workflow 文件本身而被自动触发。

---

## 5. dashboard schema 验证（未回退）

Workflow 生成的新 `dashboard_data.json`（commit `ddd0f4b`）：

| 检查项 | 结果 |
| --- | --- |
| 顶层 `runtimes` 键 | ✅ `scan` / `review` / `evolve` |
| 每个 workflow 键 | ✅ `latest` / `last_success` / `error` |
| scan latest.conclusion | `success` |
| review latest.conclusion | `success` |
| evolve latest.conclusion | `success` |
| 旧字段 `last_success_at` 残留 | ❌ 无 |
| 旧字段 `last_success_sha` 残留 | ❌ 无 |
| 旧字段 顶层 `run_id` 残留 | ❌ 无 |

---

## 6. Dashboard 页面验证

| 项目 | 结果 |
| --- | --- |
| Pages 部署 | `built`（commit `ddd0f4b`，无错误） |
| Scan 状态 | ✅ SUCCESS（Run #148） |
| Review 状态 | ✅ SUCCESS（Run #124） |
| Evolve 状态 | ✅ SUCCESS（Run #13） |
| JS error | ✅ 无 |
| console error | ✅ 无 |
| NO DATA | ✅ 未出现 |
| schema error | ✅ 未出现 |
| 页面整体 reload | ✅ 无 |

---

## Final Result

# ✅ 修复完成并验证通过

- `dashboard/fetch_runtimes.py` 已加入 `dashboard-data.yml` 的 `push.paths`，未来单独修改该文件并 push 即可自动触发数据刷新。
- 本次 push 已由 `event=push` 自动触发 workflow（run `36905057177`），`conclusion=success`。
- 新 schema（`runtimes.scan/review/evolve.latest/last_success/error`）完整保留，未回退到旧 schema。
- 未改动 schedule、其他 workflow、Runtime 代码、Dashboard 前端或数据文件，无任何旧代码删除。
