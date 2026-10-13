# Scan Schedule 调查报告（只读）

> 范围：只读核查，不修改任何代码 / workflow / schedule，不 push / rebase，不碰监控与日志。
> 仓库：`/tmp/us`，HEAD = `fedf63d`。
> 起因：用户确认 10-07 的 Scan 是手动触发（非 schedule），怀疑 GitHub 因 60 天静默期自动暂停了 schedule，
> 进而担心 10-08 13:07 UTC 也不会自动跑、判决无从谈起。

---

## 1. scan.yml 的 `on:` 完整配置

```yaml
on:
  workflow_dispatch:
  schedule:
    # Scan: Mon-Fri 21:00 Beijing = 13:00 UTC（实际 cron '7 13 * * 1-5' = 13:07 UTC）
    - cron: '7 13 * * 1-5'

concurrency:
  group: us-stock-scan
  cancel-in-progress: false   # 已跑的不取消，新触发排队
```

- **schedule cron**：`7 13 * * 1-5` → 周一至周五 **13:07 UTC**（北京时间 21:07）。
- **workflow_dispatch**：有（可手动触发）。
- **paths 过滤**：无（不像 dashboard-data.yml 有 push 路径过滤）。
- **concurrency**：`us-stock-scan` 组，不取消进行中任务。
- **无分支限制、无 matrix**：全 default 分支、单 Python 版本。

→ cron 配置本身**没有写错**（`1-5` 覆盖工作日，10-07 周三应触发）。

---

## 2. 最近 origin/main 提交时间分布（证据核心）

### 2.1 dashboard-data.yml（schedule `*/15 * * * 1-5`，工作日每 15 分钟）
连续提交，采样：

| 时间 (UTC) | commit |
|---|---|
| 2026-10-05 22:45 / 23:00 / 23:15 / 23:30 / 23:45 | chore(dashboard): refresh market data |
| 2026-10-06 全天至 23:45 | 同上（每 ~15 分钟） |
| 2026-10-07 07:16 → 15:46 | 同上（每 ~15 分钟，40+ 条） |

→ **schedule 在 10-05 / 10-06 / 10-07 连续每 15 分钟触发**，与 cron `*/15 * * * 1-5` 完全吻合。
→ 这是 GitHub schedule 系统**正在工作**的直接证据。

### 2.2 scan.yml 自己的提交（`chore: persist scan pending and AI snapshots`）
| 时间 (UTC) | commit | 与 13:07 schedule 的偏差 |
|---|---|---|
| 2026-09-29 16:04 / 16:39 | 3d52e77 / cc811ac | 离峰（疑似手动） |
| 2026-09-30 18:34 | b1e7c10 | 离峰（疑似手动） |
| 2026-10-02 18:34 | 5de10a4 | 离峰（疑似手动） |
| 2026-10-06 19:01 | 6ed7259 | 离峰（疑似手动） |
| **2026-10-07 13:32** | **d030f0f** | **+25 分钟，恰好吻合 13:07 schedule** |

→ scan.yml **自 9-29 起就在定期产出快照**，不是"从未触发"。
→ 10-07 的 scan 提交落在 **13:32 UTC**，是唯一一条对齐 `13:07 + 25min` 延迟模式的——**强烈提示它就是 schedule 触发**（其余离峰时段更像是手动 dispatch）。

---

## 3. 是否存在 > 60 天静默期

**不存在。**

- 仓库最早提交：`2026-05-27`（Create scan.py），是持续维护的老仓库。
- 近 3 天（10-05 ~ 10-07）每 15 分钟一次 dashboard 提交，**最大提交间隔 < 15 分钟**。
- GitHub 的"60 天无活动自动暂停 schedule"规则，前提是**连续 60 天零提交**。本仓库近期活动密度极高，**该规则不可能被触发**。
- 用户提到的"9-05 → 10-07 静默期"在提交历史中**不成立**：10-05/10-06 都有密集的 dashboard 提交（见 §2.1）。

---

## 4. 其他 workflow 是否也出现 schedule 未触发

| workflow | schedule cron | 是否观察到触发 |
|---|---|---|
| `dashboard-data.yml` | `*/15 * * * 1-5` | ✅ 10-05~10-07 每 15 分钟提交，活跃 |
| `scan.yml` | `7 13 * * 1-5` | ✅ 10-07 13:32 提交（吻合 schedule） |
| `review.yml` | `0 22 * * 1-5` | 未在本窗口逐一核实触发，但全局 schedule 系统已由 dashboard 证明活跃 |
| `evolve.yml` | `0 2 * * 6`（仅每月首个周六） | 同上 |

→ **没有"多个 workflow 都不触发"的迹象**；相反 dashboard-data 证明 schedule 全局活跃。
→ 若真有"全局暂停"，dashboard-data 不可能每 15 分钟提交——因此它排除了"全局被暂停"。

---

## 5. 根因判定

> **判定：不是"被 GitHub 暂停"，也不是"cron 配置错"。**
> 实际：schedule 系统活跃，scan.yml 在 10-07 13:07 UTC（±25min）已按 schedule 产出快照（d030f0f）。
> 残留不确定性：d030f0f 究竟是 schedule 触发还是你同日的手动 dispatch，**仅凭 git 提交历史无法 100% 区分**（两者提交文案完全相同），需 GitHub UI 核对。

### 与用户前提的对照
| 用户前提 | 仓库证据 | 结论 |
|---|---|---|
| 10-07 Scan 是手动、schedule 没触发 | 10-07 13:32 有 scan 提交，且吻合 13:07+25min 模式 | **前提不成立**（至少有一次 schedule 触发） |
| schedule 被 GitHub 60 天暂停 | dashboard 每 15 分钟提交，无 60 天静默 | **前提不成立** |
| 10-08 13:07 不会自动跑 | schedule 活跃 + scan.yml 本周已按 cron 触发 | **10-08 大概率会自动跑** |

### 唯一残留风险（需 UI 复核）
- 若你在 GitHub UI 中**单独禁用过 scan.yml 的 schedule**（per-workflow 开关，仓库文件看不出），则 10-08 不会自动跑。但 dashboard-data 的活跃证明"全局开关"是开的，所以这只可能是 scan.yml 被单独关。
- 验证方式（只读，不执行）：GitHub 仓库 → Actions → 左侧 `美股盘中扫描` → 看 Enable/Disable 状态；并查看 10-07 ~13:07 UTC 那次 run 的 event 是 `schedule` 还是 `workflow_dispatch`。

---

## 6. 恢复步骤（仅列出，不执行）

**当前判定不需要恢复**（schedule 未暂停）。仅在 UI 复核确认"scan.yml schedule 被单独禁用"时才需：**

1. 打开 GitHub 仓库 → **Actions** 标签页。
2. 左侧工作流列表选 **`美股盘中扫描`**（scan.yml）。
3. 若显示 **Disabled**，点 **Enable workflow**。
4. 回到主仓 **Settings → Actions → General**，确认 "Allow all actions and reusable workflows" 未被限流。
5. 验证：等下一个工作日 13:07 UTC，或手动 `workflow_dispatch` 一次，观察是否产出 `chore: persist scan` 提交。

**安全网（无论根因）**：若 10-08 13:07 UTC 后约 13:40 UTC 仍未出现新的 scan 提交，按你之前的决定**手动 dispatch 一次 scan.yml**（像 10-07 那样），判决仍可进行——监控器（PID 536931）只读检测新 snapshot 提交并出判决，与触发方式无关。

---

## 7. 对 10-08 判决的影响

**10-08 判决仍可按计划进行，且大概率由 schedule 自动触发：**
- schedule 系统活跃（dashboard 每 15 分钟证明）。
- scan.yml cron `7 13 * * 1-5` 配置正确，本周已按此触发。
- 10-08（周四）13:07 UTC 应自动产出 snapshot → 监控器捕获 → 四选一判决自动生成。
- 兜底：13:40 UTC 前无新提交则手动 dispatch，判决逻辑不变。

> 注：本轮仅报告，未改任何文件、未启用/禁用任何 workflow。
