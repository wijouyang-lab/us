# Stage 6B — Scan Schedule 只读观察报告

> 性质：**只读观察**。未修改文件/cron/workflow/代码，未 commit，未 push，未 workflow_dispatch，未 rerun，未人工制造任何测试 run。
> 观察时刻：UTC **2026-10-01 18:40**（北京 2026-10-02 02:40 / 洛杉矶 2026-10-01 11:40 PDT）
> 观察对象：`.github/workflows/scan.yml`（cron `7 13 * * 1-5` UTC）

---

## 1. Scan 最近 20 次 runs（全量）

| run_id | run# | event | status | conclusion | created_at | run_started_at | updated_at | head_sha |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 36757957242 | 148 | **schedule** | completed | success | 2026-09-30T18:21:10Z | 2026-09-30T18:21:10Z | 2026-09-30T18:35:06Z | 9737418287b7 |
| 36597992914 | 147 | workflow_dispatch | completed | success | 2026-09-29T16:28:40Z | 2026-09-29T16:28:40Z | 2026-09-29T16:39:25Z | ebb246734be4 |
| 36592484468 | 146 | workflow_dispatch | completed | success | 2026-09-29T15:44:22Z | 2026-09-29T15:44:22Z | 2026-09-29T16:04:24Z | 8314e73bf3c2 |
| 36589163783 | 145 | workflow_dispatch | completed | success | 2026-09-29T15:18:17Z | 2026-09-29T15:18:17Z | 2026-09-29T15:30:54Z | dd08b04c9119 |
| 36587440518 | 144 | workflow_dispatch | completed | success | 2026-09-29T15:04:51Z | 2026-09-29T15:04:51Z | 2026-09-29T15:15:14Z | b8bc26fc2012 |
| 36584040963 | 143 | workflow_dispatch | completed | success | 2026-09-29T14:37:22Z | 2026-09-29T14:37:22Z | 2026-09-29T14:47:51Z | 61de4fc8b2c1 |
| 36432062414 | 142 | workflow_dispatch | completed | **failure** | 2026-09-28T13:55:06Z | 2026-09-28T13:55:06Z | 2026-09-28T14:09:47Z | 5d59d3900477 |
| 36366655288 | 141 | workflow_dispatch | completed | success | 2026-09-28T01:36:58Z | 2026-09-28T01:36:58Z | 2026-09-28T01:37:29Z | c2da3ff6cfc7 |
| 36365826862 | 140 | workflow_dispatch | completed | success | 2026-09-28T01:24:05Z | 2026-09-28T01:24:05Z | 2026-09-28T01:24:31Z | c7014567134b |
| 36007834922 | 139 | workflow_dispatch | completed | **failure** | 2026-09-24T13:45:14Z | 2026-09-24T13:45:14Z | 2026-09-24T14:01:43Z | 52038ded5fce |
| 35876035476 | 138 | workflow_dispatch | completed | success | 2026-09-23T14:41:29Z | 2026-09-23T14:41:29Z | 2026-09-23T14:57:46Z | 288697404489 |
| 35871758040 | 137 | workflow_dispatch | completed | success | 2026-09-23T14:06:26Z | 2026-09-23T14:06:26Z | 2026-09-23T14:20:04Z | f719b810c9e3 |
| 35869171620 | 136 | workflow_dispatch | completed | success | 2026-09-23T13:44:23Z | 2026-09-23T13:44:23Z | 2026-09-23T13:59:43Z | a30f1d9d925c |
| 35867764676 | 135 | workflow_dispatch | completed | **failure** | 2026-09-23T13:32:21Z | 2026-09-23T13:32:21Z | 2026-09-23T13:32:56Z | 6f6a6b9688af |
| 35864084162 | 134 | workflow_dispatch | completed | **failure** | 2026-09-23T13:00:05Z | 2026-09-23T13:00:05Z | 2026-09-23T13:11:01Z | 46395c741b2b |
| 35730630302 | 133 | workflow_dispatch | completed | success | 2026-09-22T13:00:05Z | 2026-09-22T13:00:05Z | 2026-09-22T13:10:26Z | 0a52b96921d9 |
| 35687654896 | 132 | workflow_dispatch | completed | success | 2026-09-22T04:38:38Z | 2026-09-22T04:38:38Z | 2026-09-22T04:49:29Z | 90e112c7bb2a |
| 35606774543 | 131 | workflow_dispatch | completed | success | 2026-09-21T13:37:10Z | 2026-09-21T13:37:10Z | 2026-09-21T13:49:59Z | c3f2a3eda345 |
| 35604598760 | 130 | workflow_dispatch | completed | success | 2026-09-21T13:16:54Z | 2026-09-21T13:16:54Z | 2026-09-21T13:25:36Z | 1566e3b0f163 |
| 35602824222 | 129 | workflow_dispatch | completed | success | 2026-09-21T13:00:05Z | 2026-09-21T13:00:05Z | 2026-09-21T13:09:05Z | 33c5edfb597c |

**分布统计（本批次 20 条）**

| 维度 | 分布 |
| --- | --- |
| event | `schedule` × **1**， `workflow_dispatch` × 19 |
| status | `completed` × 20（`queued` 0 / `in_progress` 0） |
| conclusion | `success` × 16，`failure` × 4（**全部为 workflow_dispatch**） |

---

## 2. event=schedule 的 run 明细（全部，共 1 条）

| 字段 | 值 |
| --- | --- |
| run_id | **36757957242** |
| run_number | **148** |
| event | schedule |
| status | completed |
| conclusion | success |
| created_at | 2026-09-30T18:21:10Z |
| run_started_at | 2026-09-30T18:21:10Z |
| updated_at | 2026-09-30T18:35:06Z |
| head_sha | 9737418287b74bd0c422ec0d590a2a23bf2aea75 |

> 最近 20 次中 `event=schedule` **仅此 1 条**。

---

## 3. 理论触发点专项检查

### 关于 cron 生效时点的说明（事实）

`7724e03`（`0 13` → `7 13`）提交于 **2026-10-01 17:03:40 UTC**。因此 2026-10-01 中午触发时刻，**生效的仍是 `0 13 * * 1-5`**。下表同时列出两个口径。

| 理论触发点 | 口径 | 与观察时刻关系 | 是否出现 schedule run |
| --- | --- | --- | --- |
| 2026-09-30 13:00 UTC | 当天生效 cron `0 13` | 已过 29.63 小时 | ✅ **已出现**（run #148） |
| **2026-10-01 13:07 UTC** | 按现 cron `7 13` | **已过 5.52 小时** | ❌ **未见任何 run** |
| 2026-10-01 13:00 UTC | 当天生效 cron `0 13` | 已过 5.63 小时 | ❌ **未见任何 run** |
| **2026-10-02 13:07 UTC** | 按现 cron `7 13` | **还有 18.48 小时** | ⏳ **当前时间尚未到** |

**跨时刻复核（确认非瞬时抖动）**

| 复查时刻（UTC） | 最新 run | queued | in_progress |
| --- | --- | --- | --- |
| 18:31 | #148（2026-09-30 18:21） | — | — |
| 18:38 | #148（2026-09-30 18:21） | 0 | 0 |
| **18:40** | **#148（2026-09-30 18:21）** | **0** | **0** |

> 2026-10-01 全天无任何 Scan run，且**无排队、无运行中**的 run。

---

## 4. 已出现 schedule run 的时间计算（#148）

> 仅使用 API 提供的字段，不推断 API 未暴露的数据（如 runner 分配耗时）。

| 项目 | 值 |
| --- | --- |
| 当天生效 cron | `0 13 * * 1-5` |
| 理论触发时间 | **2026-09-30 13:00:00 UTC**（北京 21:00） |
| created_at | 2026-09-30 18:21:10 UTC（北京 2026-10-01 02:21） |
| **created_at 延迟** | **321.2 分钟（5h21m10s）** |
| run_started_at | 2026-09-30 18:21:10 UTC |
| **created_at → run_started_at** | **0 秒** |
| updated_at | 2026-09-30 18:35:06 UTC |
| **run_started_at → updated_at** | **13.9 分钟** |
| conclusion | success |

---

## 5. 缺失 schedule 记录（仅记录事实，不推测原因）

| 理论触发点 | 状态分类 | 记录 |
| --- | --- | --- |
| 2026-10-01 13:07 UTC（按现 cron） | **理论时间已过但没有 run** | 「尚未出现」。截至 2026-10-01 18:40 UTC（已过 5.52 小时），无任何对应 run；queued=0、in_progress=0 |
| 2026-10-01 13:00 UTC（当天生效 cron） | **理论时间已过但没有 run** | 「尚未出现」。截至同一时刻（已过 5.63 小时），无任何对应 run |
| 2026-10-02 13:07 UTC | **当前时间尚未到** | 「尚未出现」。距观察时刻还有 18.48 小时，属正常未到点 |

> 按上述要求：**不对 2026-10-01 缺失的原因作任何推测**（不归因于平台延迟、cron、并发或其他因素）。

---

## 6. queued / in_progress / cancelled / failure 专项核查

| 状态 | 数量 | 明细与结论 |
| --- | --- | --- |
| **queued** | **0** | 无任何排队中的 Scan run（按 `status=queued` 过滤查询确认） |
| **in_progress** | **0** | 无任何运行中的 Scan run（按 `status=in_progress` 过滤查询确认） |
| **cancelled** | 6（全库） | run #111、#109、#66、#34、#5、#4 — **全部为 `workflow_dispatch`**，时间跨度 2026-06-05 ~ 2026-09-09；**无任何 schedule run 被取消** |
| **failure** | 28（全库） | 最近 4 次为 #142（09-28）、#139（09-24）、#135（09-23）、#134（09-23）— **全部为 `workflow_dispatch`**；**无任何 schedule run 失败** |

### 理论 schedule 时间附近的 run 检查

| 时间窗 | 结果 |
| --- | --- |
| 2026-09-30 13:00 UTC 附近 | **无 run 在 13:00 附近创建**；对应 run #148 实际创建于 18:21:10（延迟 5h21m） |
| 2026-10-01 13:00 ~ 13:07 UTC 附近 | **无任何 run**（该日全天无 Scan run） |

---

## 7. 工作区只读校验

```
$ git status --short
?? dashboard/__pycache__/
?? tests/__pycache__/
```

- 无任何业务文件被修改（`M` 项为空）。
- 仅存在两个**未跟踪的 Python 缓存目录**（`__pycache__`），为运行测试时产生，非业务文件，本次观察未对其做任何改动。
- HEAD 仍为 `5d65f84`（`fix(workflow): refresh dashboard when runtime collector changes`），与上一轮一致，未产生新提交。

**结论：本次操作未修改任何业务文件，符合只读要求。**

---

## Scan Schedule 当前状态

# ⚠️ 存在疑似调度异常，需要更多样本

### 判定依据（均为可观测事实）

1. **有效 schedule 样本极少**：最近 20 次 run 中 `event=schedule` 仅 **1 条**（#148）；自 2026-09-29 引入 schedule 以来，可获得的有效触发样本为 **1 次成功 + 1 次缺失**。
2. **唯一样本延迟显著**：#148 的 `created_at` 较理论触发时间延迟 **321.2 分钟（5h21m）**，且 `created_at → run_started_at = 0 秒`（延迟不来自排队）。
3. **紧邻的下一个触发点完全缺席**：2026-10-01 理论触发点已过 **5.5 小时以上**，截至观察时刻 **无任何 run**，且 `queued = 0`、`in_progress = 0`（不是"排队中尚未启动"）。
4. **排除项（已证实非此类问题）**：无 schedule run 被 cancelled、无 schedule run 失败、无 push 触发导致的双跑、cron 语法与时区换算均正确。

### 为何不是另外两项

- **不是「已确认调度异常」**：样本量仅 1 次成功触发，不足以区分"GitHub Actions scheduled run 的平台延迟"与"本次未触发"；对 2026-10-01 的缺失，现有数据**无法证明成因**，故不作因果定性。
- **不是「正常观察中」**：单次 321 分钟延迟已属显著；且下一个触发点逾期 5.5 小时仍完全无 run（非排队），已超出正常观察的范畴。

### 建议的后续观察（不改变任何配置）

- 关注 **2026-10-02 13:07 UTC**（北京 2026-10-02 21:07）是否出现 `event=schedule` 的 run；
- 若出现，记录其 `created_at` 延迟，与 #148 的 321.2 分钟对比，以积累样本；
- 若仍未出现，且 `queued` 持续为 0，则异常样本数将增至 2，届时可提升判定等级。

> 本报告**未修改任何 Schedule 配置**，也**未基于单次延迟提出任何 cron 修改方案**。
