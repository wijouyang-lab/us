# 调度触发调查：Review / Scan 的 GitHub Schedule 是否真的在触发？

> 生成时间：2026-10-11（只读调查，未改代码、未 push）
> 关键限制（先讲清楚）：本仓库为**私有**，且当前环境**无 GitHub token**（`gh` 未登录、`GH_TOKEN`/`GITHUB_TOKEN` 均未设置）。
> 因此 **`gh run list` 的实时触发源数据我无法获取**，第 1/2/3 节「event 分布」无法用真实 run 填充。
> 本文以**静态配置分析（workflow 文件的 `on:` 块）** 为主证据，并给出你可在本地一键核实实时数据的命令。

---

## 0. 我查了什么 / 没查到什么

| 调查项 | 方法 | 结果 |
|---|---|---|
| 实时 run 触发源（event） | `gh run list` / GitHub API | ❌ 无法获取（私有仓库 + 无 token，匿名 API 返回 404） |
| workflow 文件 `on:` 触发器配置 | 直接读 `.github/workflows/*.yml` | ✅ 已获取（决定性证据） |
| schedule 是否被 UI 手动 disable | `gh workflow list` 状态列 | ❌ 无法获取（同上） |

**结论前提**：以下对「是否在触发」的判断，scan 是**配置级确定性结论**（文件里就没有 schedule），review/dashboard-data 是**配置级有效结论**（文件里有合法的 schedule）；但「过去 N 次是否真的 fired」需你用第 6 节命令核实。

---

## 1. Review 最近 run 的 event 分布（静态 + 待核实）

**静态配置**（`review.yml` 顶部）：
```yaml
on:
  workflow_dispatch:
  schedule:
    # Review: Tue-Sat 06:00 Beijing = Mon-Fri 22:00 UTC
    - cron: '23 22 * * 1-5'
```
- Review **有** schedule：`23 22 * * 1-5` = 周一~周五 22:23 UTC = 北京 **周二~周六 06:23**（美股每个交易日收盘后）。
- 配置本身合法，**没有隐藏缺陷**（不存在被注释、缩进错误、字段写错等问题）。
- ⚠️ 注释文字写「Tue-Sat 06:00」与 cron 的 22:23 略有出入，但 cron 字段 `1-5`（周一~周五）是正确的，仅为注释不精确，不影响触发。

**实时 event 分布**：见第 6 节命令核实。配置层面 review「应该有 schedule 触发」，但「实际有没有 fired、是不是每次都是你手动 dispatch」我无法从静态数据判定——需你跑命令。

---

## 2. Scan 最近 run 的 event 分布（静态 + 决定性）

**静态配置**（`scan.yml` 顶部）：
```yaml
on:
  workflow_dispatch:
```
- Scan **完全没有 `schedule:` 块**——`on:` 下只有 `workflow_dispatch:`。
- 这是**确定性结论**：scan **从设计上就是「仅手动触发」**，GitHub 没有任何定时任务会去跑它。
- 这**完美解释了你观察的事实**：「之前的 scan 多次是手动触发」不是 bug，而是因为它**压根没有 schedule**。任何 scan run 都是 `workflow_dispatch`（手动）或别的 workflow 调起——但 `news-fetch.yml` 是 `workflow_call` 被 scan 调，反向不成立；`quant-research.yml` 也是 call，不会调 scan。所以 scan 的触发源**只有手动**。

> 一句话：scan 的 schedule「从来没工作过」是因为**它从来就不存在**。根因 = 缺 schedule 配置，不是被暂停或失效。

---

## 3. Dashboard-data 的对照（为什么它的 schedule 工作）

**静态配置**（`dashboard-data.yml` 顶部）：
```yaml
on:
  schedule:
    - cron: "*/15 * * * 1-5"   # 工作日每 15 分钟
  workflow_dispatch:
    inputs: {...}
  push:
    paths: [dashboard_export.py, ...]
```
- 它有合法 `schedule:`（工作日每 15 分钟）+ `push`（改 export 即触发）+ dispatch。
- 与你「dashboard-data 的 schedule 正常工作」的观察**一致**——因为它确实有 schedule 块。

**横向对比表**

| Workflow | `on:` 触发器 | 有没有 schedule | 预期能否自动触发 |
|---|---|---|---|
| `scan.yml` | `workflow_dispatch` | ❌ **无** | 否（仅手动） |
| `review.yml` | `workflow_dispatch` + `schedule` | ✅ 有（`23 22 * * 1-5`） | 是（配置合法） |
| `dashboard-data.yml` | `schedule` + `dispatch` + `push` | ✅ 有（`*/15 * * * 1-5`） | 是 |
| `evolve.yml` | `workflow_dispatch` + `schedule` | ✅ 有（`0 2 1 * *`） | 是（每月 1 号） |
| `news-fetch.yml` | `workflow_call` + `dispatch` | ❌ 无（被 scan 调） | 否（由 scan 触发） |
| `quant-research.yml` | `workflow_dispatch` + `workflow_call` | ❌ 无 | 否（被 call） |

---

## 4. Schedule 是否被暂停 / 禁用

**GitHub 的 60 天规则不适用**：
- 规则原文：仓库若 **60 天内无任何 commit/push 活动**，GitHub 会暂停该仓库所有 scheduled workflows。
- 本仓库**每天多次 push**（dashboard-data 每 15 分钟刷新 + 其它提交），远未触达 60 天阈值。
- 因此「整仓库 schedule 被暂停」**不是根因**——这也解释了 dashboard-data 的 schedule 为何照常工作（它没被暂停）。

**是否被 UI 手动 disable（无法静态判定）**：
- GitHub 允许在 Actions 页面单独禁用某个 workflow 的 schedule。
- 这种禁用**不会改变 workflow 文件内容**（所以我在仓库里看不出），只能通过 `gh workflow list` 的「disabled」状态或 API `state` 字段查到。
- 这是「review 的 schedule 有没有真的工作」唯一无法从文件排除的可能——需你用第 6 节命令核实。

---

## 5. 关键判断

1. **Scan 的 schedule 从来没工作过吗？**
   → 是的，且是**确定的、设计性的**：`scan.yml` 的 `on:` 里**根本没有 schedule 块**。它不是「失效」，而是「不存在」。

2. **根因是什么？**
   - **Scan**：缺 schedule 配置。要恢复自动扫描，需在 `scan.yml` 的 `on:` 加 `schedule:` 块（并确认 cron 时区——GitHub cron **只认 UTC**）。
   - **Review**：配置里 schedule 是合法的，静态层面找不出缺陷。若它实际也没自动跑，唯一剩下的非代码原因是「在 GitHub UI 被手动 disable」或「你记错了（因为 schedule 是 Mon-Fri，周六的手动 run 本就不在排程内）」。

3. **Dashboard-data 的 schedule 为什么工作？**
   → 因为它确实有 `schedule:` 块，且仓库活跃（60 天规则不适用），也没有被禁用迹象。配置 + 环境都满足，所以正常触发。

4. **一句话总结**
   > Scan 的「手动触发」是**缺配置**导致的必然结果；Review 的「疑似不工作」在文件层面看不出原因，需核实是否被 UI 禁用；Dashboard-data 工作正常因为它配置齐全。三者差异的根因是**各自 workflow 文件里有没有写 schedule**，而非同一套调度机制时好时坏。

---

## 6. 你可在本地一键核实的实时命令

（需先 `gh auth login` 或 `export GH_TOKEN=...`；仓库私有，必须带 token）

```bash
# 1) 三个 workflow 最近 run 的 触发源 + 时间 + 状态
gh run list --repo wijouyang-lab/us --workflow=scan.yml        --limit 20 --json event,createdAt,status,conclusion
gh run list --repo wijouyang-lab/us --workflow=review.yml      --limit 20 --json event,createdAt,status,conclusion
gh run list --repo wijouyang-lab/us --workflow=dashboard-data.yml --limit 20 --json event,createdAt,status,conclusion

# 2) 检查是否有 workflow 被 UI 手动禁用（状态列会显示 disabled）
gh workflow list --repo wijouyang-lab/us

# 3) 精确看某个 workflow 的启用状态（state 字段：active / disabled_manually / disabled_inactivity）
gh api repos/wijouyang-lab/us/actions/workflows --jq '.workflows[] | {name, state, path}'
```

**判读标准**：
- 若 `scan.yml` 的所有 run `event` 全是 `workflow_dispatch`、零 `schedule` → 与本文结论一致（它没有 schedule）。
- 若 `review.yml` 有 `event: schedule` 的 run → 说明它的 schedule 确实工作过，你之前的怀疑需修正。
- 若 `gh workflow list` 里 review/scan 显示 `disabled` → 这就是 review 不自动跑的真因（需在 UI 重新 Enable）。

---

## 7. 建议（仅调研结论，未实施）

| 优先级 | 建议 | 说明 |
|---|---|---|
| 🔴 高 | 给 `scan.yml` 补 `schedule:` 块 | 当前 scan 完全依赖手动。按北京时间 21:00 盘前扫描，对应 UTC 13:00，cron 例：`0 13 * * 1-5`（周一~周五）。**注意 GitHub cron 只认 UTC**。 |
| 🟡 中 | 核实 review 是否被 UI 禁用 | 跑第 6 节命令；若 `disabled_manually` 则在 Actions 页面 Enable。 |
| 🟡 中 | 修正 review.yml 注释 | 「Tue-Sat 06:00 Beijing = Mon-Fri 22:00 UTC」与 cron 22:23 不符，改为「Mon-Fri 22:23 UTC = Tue-Sat 06:23 Beijing」。 |
| 🟢 低 | 给 scan 加与 review 一致的 `concurrency` 防重入 | 当前 scan 已有 `us-stock-scan` 组，但要确认自动触发后不会与手动冲突（已 `cancel-in-progress: false`，OK）。 |

---

## 8. 铁律确认
- 本文为**只读调查**：只读取 `.github/workflows/*.yml` 与 `git remote`，**未改任何代码/workflow**。
- 未执行 `git push` / `git rebase`。
- 未触碰任何监控/运行中的 job。
- 实时 run 数据因无 token 未能获取，已在第 0、6 节如实标注并给出核实命令，未编造 event 分布。
