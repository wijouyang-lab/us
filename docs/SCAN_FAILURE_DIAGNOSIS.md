# 美股盘中扫描失败 · 只读诊断报告

> 诊断时间：2026-10-06 10:47–10:57 UTC
> 全程只读：未修改任何文件、未 commit、未 push、未 dispatch、未 rerun、未修改 workflow。

---

## 一、失败的 Run

| 字段 | 值 |
|---|---|
| **Run ID** | `37373620155` |
| **Run Number** | **150** |
| Name | 美股盘中扫描 |
| **event** | `schedule`（自然定时触发，非 dispatch） |
| created_at | `2026-10-05T21:04:23Z` |
| run_started_at | `2026-10-05T21:04:23Z` |
| updated_at | `2026-10-05T21:19:27Z` |
| status | `completed` |
| **conclusion** | **`failure`** |
| head_sha | `110d15dd50a5e1485d5186ca314c458a21dac985` |
| head_branch | `main` |
| head_commit message | `chore(dashboard): refresh market data [skip ci]` |
| workflow path | `.github/workflows/scan.yml` |
| actor | `wijouyang-lab` |
| attempt | 1（**无 rerun**） |
| html_url | https://github.com/wijouyang-lab/us/actions/runs/37373620155 |

**该 Run 有 job**（不是空 run）。

---

## 二、Jobs 与 Steps

| 项 | 值 |
|---|---|
| **jobs 数量** | **1** |
| job_id | `111976601365` |
| name | `scan` |
| status / conclusion | `completed` / **`cancelled`** |
| started_at | `2026-10-05T21:04:24Z` |
| completed_at | `2026-10-05T21:19:27Z`（**滞留 15m03s**） |
| **runner_name** | **空（从未分配到 runner）** |
| labels | `ubuntu-latest` |
| **steps 数量** | **0** |

### 逐个 step

**无 —— steps 数量为 0，一个 step 都没有生成。**

### 情况判定

| 候选 | 判定 | 依据 |
|---|---|---|
| A. job 根本没有创建 | ❌ | jobs=1，job_id 存在 |
| **B. job 创建了但 0 steps** | ✅ **命中** | steps=0、runner_name 空、无日志 |
| C. job/steps 都有但 UI 显示无步骤 | ❌ | API 层面 steps 确实为 0 |
| D. workflow 被 skipped | ❌ | conclusion=failure，非 skipped |
| E. workflow 被 cancelled | ⚠️ 部分 | job conclusion=cancelled，但这是**结果**不是原因 |
| F. startup_failure | ❌ | 无 startup_failure 标记，run 正常创建 |
| **G. runner 根本没有启动** | ✅ **命中** | runner_name 空 + 官方注解明说未被 runner 获取 |
| H. YAML 解析异常 | ❌ | 参见第四节，文件正常且 job 正常创建 |
| I. scan.py 失败 | ❌ | scan.py **从未执行**（0 steps） |

---

## 三、Job 日志

- 日志下载返回 `BlobNotFound`：**该 job 没有任何日志产物**（因为从未有 runner 执行它）
- 无 traceback、无 exit code、无 checkout / setup-python / pip install / python scan.py 的任何痕迹

**结论：scan.py 从未被执行，因此不存在 scan.py 层面的错误。**

---

## 四、Workflow 文件实际版本

| 对比项 | 结果 |
|---|---|
| 失败 Run 的 head_sha `110d15dd` 对应 scan.yml | 135 行 |
| 当前 main 的 scan.yml | 135 行 |
| 两者差异 | ✅ **完全一致** |

失败时刻生效的配置（与该 commit 一致）：

```yaml
on:
  workflow_dispatch:
  schedule:
    - cron: '7 13 * * 1-5'
concurrency:
  group: us-stock-scan
  cancel-in-progress: false
jobs:
  scan:
    runs-on: ubuntu-latest
```

- 未设置 `timeout-minutes`（默认 360 分钟），**不是自建超时导致**
- cron 仍为 `7 13 * * 1-5`
- concurrency 仍为 `cancel-in-progress: false`

**该 Run 的 head commit 是 Dashboard Data 自动提交**（`chore(dashboard): refresh market data [skip ci]`），不是 Scan 代码提交 —— 这是 scheduled workflow 的正常行为（跑在 main 最新提交上）。

---

## 五、最近 Git 历史

最近 25 个 commit **全部**是 `github-actions[bot]` 的 `chore(dashboard): refresh market data [skip ci]` 自动数据提交。

非 dashboard-data 的 commit（最近 60 个内）：

| commit | 时间 | 作者 | 标题 |
|---|---|---|---|
| `3590411` | 2026-10-06 02:11 UTC | github-actions[bot] | `chore: 美股盘后补充成交 2026-10-06` |

失败前 4 个 commit：

| commit | 时间 | 标题 |
|---|---|---|
| `110d15dd` | 2026-10-05 20:28 | chore(dashboard): refresh market data |
| `11eba19` | 2026-10-05 19:05 | chore(dashboard): refresh market data |
| `61b5b3c` | 2026-10-05 18:45 | chore(dashboard): refresh market data |
| `bd13337` | 2026-10-05 18:30 | chore(dashboard): refresh market data |

- **无 workflow 文件变化**
- **无 concurrency 变化**
- **无 merge / rebase**
- **无 Scan 代码提交**

---

## 六、并发 / 排队情况

| 检查 | 结果 |
|---|---|
| 当前 queued 的 Scan | **0** |
| 当前 in_progress 的 Scan | **0** |
| 是否有第二个 Scan 抢占 | **否**（#150 是唯一，且无 #151） |
| `us-stock-scan` group 是否被其它 workflow 共用 | **否**（仅 scan.yml） |
| 无 rerun / attempt | ✅ attempts=0 |

`cancel-in-progress: false` 行为符合预期 —— 没有任何 run 因并发被取消。

---

## 七、GitHub Check 状态

commit `110d15dd` 的 check_runs 共 **7** 个：

| check name | status | conclusion | 时间窗口 |
|---|---|---|---|
| **scan** | completed | **cancelled** | 21:04:24 → 21:19:27 |
| refresh | completed | success | 21:10:37 → 21:11:25 |
| refresh | completed | **cancelled** | 20:45:11 → 21:00:13 |
| refresh | completed | **cancelled** | 20:30:08 → 20:45:09 |
| **build**（Pages） | completed | **cancelled** | 20:28:06 → 20:43:07 |
| deploy（Pages） | completed | skipped | 20:43 |
| report-build-status | completed | success | 20:53 |

**关键：GitHub 自己托管的 Pages build 也在同一时段被 cancelled。** 这排除了"本仓库某 workflow 配置问题"的可能 —— 仓库配置无法影响 GitHub Pages 官方 workflow。

---

## 八、★★★ 决定性证据 ★★★

Scan job 的 **check-run annotations**：

```
The job was not acquired by Runner of type hosted even after multiple attempts
```

同一时段 dashboard-data 的两个 cancelled job（run 37371669760 / 37370114348）也带**完全相同**的注解：

```
The job was not acquired by Runner of type hosted even after multiple attempts
```

即：**GitHub 托管 runner 多次尝试后仍未获取到该 job** → job 滞留队列 → 约 15 分钟后被取消 → 未产生任何 step → UI 显示「此检查没有步骤」。

---

## 九、影响范围（同一时段，跨 workflow）

| workflow | run | 窗口 | 时长 | steps | 结论 |
|---|---|---|---|---|---|
| Pages build | — | 20:28:06 → 20:43:07 | 15m01s | 0 | cancelled |
| dashboard-data | #1286 | 20:30:08 → 20:45:09 | 15m01s | 0 | cancelled |
| dashboard-data | #1288 | 20:45:11 → 21:00:13 | 15m02s | 0 | cancelled |
| **美股盘中扫描** | **#150** | **21:04:24 → 21:19:27** | **15m03s** | **0** | **cancelled** |

2026-10-05 全天 dashboard-data 失败 6 次（19:15 / 19:30 / 19:45 / 20:00 / 20:30 / 20:45）+ 取消 1 次（20:34），全部集中在 **19:15–21:00 UTC 这个窗口**；21:00 之后恢复正常。

Scan #150 恰好落在该窗口的尾部（21:04–21:19）。

---

## 十、逐题回答

| # | 问题 | 回答 |
|---|---|---|
| 1 | 失败的是哪个 Run？ | 美股盘中扫描 **#150** |
| 2 | Run ID？ | **37373620155** |
| 3 | 有没有 Job？ | **有** |
| 4 | 有几个 Job？ | **1** 个（`scan`） |
| 5 | 有几个 Step？ | **0 个** |
| 6 | 「此检查没有步骤」发生在哪一层？ | **Runner 分配层**：job 已创建但从未被 runner 获取，因此无任何 step 被实例化 |
| 7 | Scan job 是否真正启动？ | **否** —— `runner_name` 为空、无日志、无 step |
| 8 | scan.py 是否真正执行？ | **从未执行** |
| 9 | 若执行，哪一步失败？ | 不适用（未执行） |
| 10 | 若未执行，为什么？ | GitHub 托管 runner 多次尝试未获取该 job（官方注解），滞留约 15 分钟后被取消 |
| 11 | 是否与 Dashboard Data 有关？ | **否**。仅因 scheduled run 跑在 dashboard-data 的自动 commit 上（正常）；该 commit 本身不是成因。但同期 dashboard-data 也受同一平台问题影响 |
| 12 | 是否与 concurrency 有关？ | **否**。无并发 run、无抢占、无 queued 积压；group 只被 scan.yml 使用 |
| 13 | 是否与最近 commit 有关？ | **否**。失败前后无任何 workflow / 代码变更 |
| 14 | 是否是 GitHub Actions 平台/runner 问题？ | **是** |
| 15 | 是否是 workflow YAML 问题？ | **否**（文件一致、job 正常创建） |
| 16 | 是否是 scan.py 问题？ | **否**（从未执行） |

---

## 【Root Cause】

# C. Runner / 平台问题

**具体表述**：2026-10-05 约 19:15–21:19 UTC 期间，GitHub Actions 托管 runner 出现区域性获取失败；本 Run 的 job 已创建并进入队列，但 **GitHub 托管 runner 多次尝试仍未获取该 job**（官方注解原文：`The job was not acquired by Runner of type hosted even after multiple attempts`），滞留约 15 分钟后被系统取消。因 job 从未被 runner 接管，未生成任何 step、未产生任何日志，故 GitHub UI 显示「此检查没有步骤」。

排除项：非 workflow 配置、非 concurrency、非 commit 变更、**非 scan.py**、非依赖/环境、非 API/网络（业务侧）。

## 【Confidence】

# High

依据：GitHub 官方 check-run annotation 直接给出原因文本；同一时段本仓库 dashboard-data（2 个 job）与 **GitHub 官方托管的 Pages build** 均出现完全相同的注解与 15 分钟取消特征；无任一反证指向仓库侧配置或代码。

---

## 附带观察（非本次失败成因，仅记录）

1. **Schedule 延迟仍然存在**：本次 Run cron 应为 `13:07 UTC`，实际 `created_at = 2026-10-05T21:04:23Z`，延迟约 **7 小时 57 分**。与此前 Stage 6B/6C 观察到的 schedule 延迟现象一致，但**不是**本次失败的原因。
2. **今日（2026-10-06）Scan 尚未触发**：当前 UTC 10:57，cron 触发点 13:07 UTC 未到；最新 Scan 仍为 #150。

## 建议（未执行任何操作）

- 无需修改任何代码或 workflow —— 这是平台侧瞬时故障。
- 若要尽快补一次 Scan，需你明确授权 `workflow_dispatch`（本次未执行）。
- 可关注 https://www.githubstatus.com 的 Actions 组件状态确认是否有对应事件记录。

---

## 只读性确认

| 项 | 值 |
|---|---|
| Files modified | **0** |
| Commits | **0** |
| Pushes | **0** |
| Dispatches | **0** |
| Reruns | **0** |
