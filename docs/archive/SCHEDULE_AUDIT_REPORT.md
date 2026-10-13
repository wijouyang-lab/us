# Schedule 只读审计报告 — Scan / Review / Evolve

> 审计性质：**只读**。未修改任何文件、未 commit、未 push、未手动 dispatch 任何 workflow。
> 审计时刻：UTC 2026-10-01 18:32（北京 2026-10-02 02:32 / 洛杉矶 2026-10-01 11:32 PDT）

---

## A. 当前 Schedule 配置

| Workflow | 名称 | Cron（UTC） | UTC 触发 | 北京时间 | 洛杉矶时间（PDT） | workflow_dispatch | push / paths |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `scan.yml` | 美股盘中扫描 | `7 13 * * 1-5` | 周一~周五 13:07 | 周一~周五 21:07 | 周一~周五 06:07 | ✅ 有（无 inputs） | ❌ 无 |
| `review.yml` | 美股盘后复盘 | `0 22 * * 1-5` | 周一~周五 22:00 | 周二~周六 06:00 | 周一~周五 15:00 | ✅ 有（无 inputs） | ❌ 无 |
| `evolve.yml` | US-Share Evolve | `0 2 * * 6` | 每周六 02:00 | 每周六 10:00 | 每周五 19:00 | ✅ 有（无 inputs） | ❌ 无 |

### 配置补充说明

| 项目 | 说明 |
| --- | --- |
| 时区 | 三个 workflow **均无** `timezone` 字段，使用 GitHub 原生 UTC cron。已于 `dd11d91`（2026-09-30）从错误的 `timezone: Asia/Shanghai` 写法修正为显式 UTC。 |
| concurrency | Scan：`us-stock-scan` / `cancel-in-progress: false`；Review：`us-stock-review` / `cancel-in-progress: false`；Evolve：**无** concurrency 配置。 |
| Evolve 特殊逻辑 | cron 每周六触发，但 workflow 内含 `Check first Saturday of month` 步骤：仅当北京时间 `dow=6` 且 `day-of-month <= 7` 时才执行业务；其余周六创建 run 后跳过业务。手动 dispatch 不受此限制。 |
| 三个 workflow state | 均为 `active` |

### Cron 变更沿革（证据：git log）

| Commit | 时间 | scan | review | evolve |
| --- | --- | --- | --- | --- |
| `61de4fc` | 2026-09-29 22:34 +0800（首次引入 schedule，带 timezone） | `0 21 * * 1-5` | `0 6 * * 2-6` | `0 10 * * 6` |
| `dd11d91` | 2026-09-30 08:22 +0800（改显式 UTC） | `0 13 * * 1-5` | `0 22 * * 1-5` | `0 2 * * 6` |
| `7724e03` | 2026-10-02 01:03 +0800（Scan 避开整点） | `7 13 * * 1-5` | 未变 | 未变 |

---

## B. 最近实际运行记录

### B1. Scan — 最近 10 次

| run_id | event | status | conclusion | run# | created_at | run_started_at | updated_at | head_sha |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 36757957242 | **schedule** | completed | success | 148 | 2026-09-30T18:21:10Z | 2026-09-30T18:21:10Z | 2026-09-30T18:35:06Z | 9737418287b7 |
| 36597992914 | workflow_dispatch | completed | success | 147 | 2026-09-29T16:28:40Z | 2026-09-29T16:28:40Z | 2026-09-29T16:39:25Z | ebb246734be4 |
| 36592484468 | workflow_dispatch | completed | success | 146 | 2026-09-29T15:44:22Z | 2026-09-29T15:44:22Z | 2026-09-29T16:04:24Z | 8314e73bf3c2 |
| 36589163783 | workflow_dispatch | completed | success | 145 | 2026-09-29T15:18:17Z | 2026-09-29T15:18:17Z | 2026-09-29T15:30:54Z | dd08b04c9119 |
| 36587440518 | workflow_dispatch | completed | success | 144 | 2026-09-29T15:04:51Z | 2026-09-29T15:04:51Z | 2026-09-29T15:15:14Z | b8bc26fc2012 |
| 36584040963 | workflow_dispatch | completed | success | 143 | 2026-09-29T14:37:22Z | 2026-09-29T14:37:22Z | 2026-09-29T14:47:51Z | 61de4fc8b2c1 |
| 36432062414 | workflow_dispatch | completed | **failure** | 142 | 2026-09-28T13:55:06Z | 2026-09-28T13:55:06Z | 2026-09-28T14:09:47Z | 5d59d3900477 |
| 36366655288 | workflow_dispatch | completed | success | 141 | 2026-09-28T01:36:58Z | 2026-09-28T01:36:58Z | 2026-09-28T01:37:29Z | c2da3ff6cfc7 |
| 36365826862 | workflow_dispatch | completed | success | 140 | 2026-09-28T01:24:05Z | 2026-09-28T01:24:05Z | 2026-09-28T01:24:31Z | c7014567134b |
| 36007834922 | workflow_dispatch | completed | **failure** | 139 | 2026-09-24T13:45:14Z | 2026-09-24T13:45:14Z | 2026-09-24T14:01:43Z | 52038ded5fce |

> **schedule 事件占比：1 / 10**。唯一 schedule run 为 #148（2026-09-30）。

### B2. Review — 最近 10 次

| run_id | event | status | conclusion | run# | created_at | run_started_at | updated_at | head_sha |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 36799795650 | **schedule** | completed | success | 124 | 2026-10-01T01:10:15Z | 2026-10-01T01:10:15Z | 2026-10-01T01:12:45Z | e42525140c43 |
| 36688871161 | workflow_dispatch | completed | success | 123 | 2026-09-30T08:18:14Z | 2026-09-30T08:18:14Z | 2026-09-30T08:21:13Z | f8cc89d3193c |
| 36683400093 | workflow_dispatch | completed | success | 122 | 2026-09-30T07:23:21Z | 2026-09-30T07:23:21Z | 2026-09-30T07:26:16Z | 19021f6adbd6 |
| 36681252633 | workflow_dispatch | completed | success | 121 | 2026-09-30T07:00:18Z | 2026-09-30T07:00:18Z | 2026-09-30T07:04:22Z | 01ad3c071ad4 |
| 36677264105 | workflow_dispatch | completed | success | 120 | 2026-09-30T06:14:57Z | 2026-09-30T06:14:57Z | 2026-09-30T06:18:16Z | b469fd31dcc1 |
| 36672989601 | workflow_dispatch | completed | success | 119 | 2026-09-30T05:20:57Z | 2026-09-30T05:20:57Z | 2026-09-30T05:24:30Z | 590a5c913489 |
| 36669495461 | workflow_dispatch | completed | success | 118 | 2026-09-30T04:35:03Z | 2026-09-30T04:35:03Z | 2026-09-30T04:38:13Z | 64b84249a6d0 |
| 36668220625 | workflow_dispatch | completed | success | 117 | 2026-09-30T04:18:11Z | 2026-09-30T04:18:11Z | 2026-09-30T04:21:00Z | 094761a23538 |
| 36667548189 | workflow_dispatch | completed | success | 116 | 2026-09-30T04:09:05Z | 2026-09-30T04:09:05Z | 2026-09-30T04:13:31Z | 48bc8ec15ec7 |
| 36666925200 | workflow_dispatch | completed | **failure** | 115 | 2026-09-30T04:00:24Z | 2026-09-30T04:00:24Z | 2026-09-30T04:01:01Z | 60f0466d96fb |

> **schedule 事件占比：1 / 10**。唯一 schedule run 为 #124（对应 2026-09-30 22:00 UTC 触发点）。

### B3. Evolve — 最近 10 次（仓库历史共 13 次）

| run_id | event | status | conclusion | run# | created_at | run_started_at | updated_at | head_sha |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 33937804241 | workflow_dispatch | completed | success | 13 | 2026-09-05T02:00:06Z | 2026-09-05T02:00:06Z | 2026-09-05T02:00:34Z | e32b5ef89246 |
| 32592400773 | workflow_dispatch | completed | success | 12 | 2026-08-22T19:00:05Z | 2026-08-22T19:00:05Z | 2026-08-22T19:00:36Z | c62c6430f370 |
| 31902673482 | workflow_dispatch | completed | success | 11 | 2026-08-15T19:00:04Z | 2026-08-15T19:00:04Z | 2026-08-15T19:01:19Z | 385a51461fb4 |
| 31273322114 | workflow_dispatch | completed | success | 10 | 2026-08-08T19:00:04Z | 2026-08-08T19:00:04Z | 2026-08-08T19:01:32Z | f6d151f8d617 |
| 30713797162 | workflow_dispatch | completed | success | 9 | 2026-08-01T19:00:03Z | 2026-08-01T19:00:03Z | 2026-08-01T19:01:36Z | a5cb6879df58 |
| 30170740118 | workflow_dispatch | completed | success | 8 | 2026-07-25T19:00:06Z | 2026-07-25T19:00:06Z | 2026-07-25T19:01:15Z | 4c2839d4bc1c |
| 29692423606 | workflow_dispatch | completed | success | 7 | 2026-07-19T15:14:07Z | 2026-07-19T15:14:07Z | 2026-07-19T15:15:24Z | 6be0d6cf1687 |
| 29656949249 | workflow_dispatch | completed | success | 6 | 2026-07-18T19:00:07Z | 2026-07-18T19:00:07Z | 2026-07-18T19:02:45Z | 1ac5b85510ed |
| 29164480010 | workflow_dispatch | completed | success | 5 | 2026-07-11T19:00:06Z | 2026-07-11T19:00:06Z | 2026-07-11T19:00:53Z | 63ef9d20e8b1 |
| 28716455593 | workflow_dispatch | completed | success | 4 | 2026-07-04T19:00:07Z | 2026-07-04T19:00:07Z | 2026-07-04T19:01:01Z | 84a944c0d366 |

> **schedule 事件占比：0 / 13（全量历史核查）**。Evolve 自建库以来全部为手动 dispatch，**从未出现 schedule 触发**。

---

## C. 理论时间 vs 实际时间

### C1. Scan run #36757957242（唯一 schedule run）

| 项目 | 值 |
| --- | --- |
| 触发日 | 2026-09-30（周三，落在 `1-5` 内） |
| 当时生效 cron | `0 13 * * 1-5`（`7724e03` 改 `7 13` 是 2026-10-01 17:03 UTC，晚于本次） |
| 理论触发 | **2026-09-30 13:00:00 UTC**（北京 21:00） |
| 实际 created_at | **2026-09-30 18:21:10 UTC**（北京 2026-10-01 02:21） |
| run_started_at | 2026-09-30 18:21:10 UTC |
| updated_at | 2026-09-30 18:35:06 UTC |
| conclusion | success |

延迟拆解：

| 类别 | 时长 | 证据 |
| --- | --- | --- |
| **a. GitHub schedule 触发延迟** | **321.2 分钟（5h21m）** | 理论 13:00 → 实际 created 18:21:10 |
| b. schedule 已创建但排队 | **0 秒** | `created_at` == `run_started_at`（18:21:10） |
| c. runner 启动延迟 | **无法证明** | API 不暴露 runner 分配耗时；`created==started` 说明无排队等待 |
| d. workflow 内部耗时 | **13.9 分钟** | `started 18:21:10` → `updated 18:35:06` |

### C2. Review run #36799795650（唯一 schedule run）

| 项目 | 值 |
| --- | --- |
| 触发日 | 对应 2026-09-30（周三，落在 `1-5` 内）的 22:00 UTC 触发点 |
| 当时生效 cron | `0 22 * * 1-5` |
| 理论触发 | **2026-09-30 22:00:00 UTC**（北京 2026-10-01 06:00） |
| 实际 created_at | **2026-10-01 01:10:15 UTC**（北京 09:10） |
| run_started_at | 2026-10-01 01:10:15 UTC |
| updated_at | 2026-10-01 01:12:45 UTC |
| conclusion | success |

延迟拆解：

| 类别 | 时长 | 证据 |
| --- | --- | --- |
| **a. GitHub schedule 触发延迟** | **190.2 分钟（3h10m）** | 理论 22:00 → 实际 created 次日 01:10:15 |
| b. schedule 已创建但排队 | **0 秒** | `created_at` == `run_started_at` |
| c. runner 启动延迟 | **无法证明** | 同上 |
| d. workflow 内部耗时 | **2.5 分钟** | `started 01:10:15` → `updated 01:12:45` |

### C3. Scan 2026-10-01 触发点（缺失观察）

| 项目 | 值 |
| --- | --- |
| 理论触发 | **2026-10-01 13:00:00 UTC**（北京 21:00；当时 cron 仍为 `0 13`） |
| 审计时刻 | 2026-10-01 18:32:40 UTC |
| 已过时長 | **332.7 分钟（5h33m）** |
| 实际 | **截至审计时刻无任何 2026-10-01 的 Scan run**（复查确认最新 run 仍为 2026-09-30 18:21） |

> 对照：前一次（9/30）同类延迟为 321.2 分钟。按该量级推算，10/01 的 run 预期约在 18:21 UTC 出现；审计时刻 18:32 已超出该时点约 11 分钟，仍未出现。
> **定性：客观事实是"截至审计时刻未出现"；其成因（仍在队列 / 本次未触发）当前数据无法证明，不作结论。**

### C4. Evolve 首次 schedule 触发点（尚未发生）

| 项目 | 值 |
| --- | --- |
| cron | `0 2 * * 6`（每周六 UTC 02:00） |
| schedule 引入时间 | `61de4fc`，2026-09-29 22:34 +0800（= 2026-09-29 14:34 UTC） |
| 引入后首个周六 | **2026-10-03** |
| 首次理论触发 | **2026-10-03 02:00:00 UTC** |
| 北京时间 | **2026-10-03 10:00:00 周六**（day-of-month = 3 ≤ 7，dow = 6 → 满足"每月第一个周六"，业务会执行） |
| 洛杉矶时间 | **2026-10-02 19:00:00 周五**（PDT） |
| 距审计时刻 | **还有 31.5 小时 → 尚未发生** |

> **未手动 dispatch 代替验证**（本次审计为只读，禁止为验证而触发 workflow）。

---

## D. 异常（仅列有证据支持者）

| # | 异常 | 证据 | 定性 |
| --- | --- | --- | --- |
| 1 | **Scan schedule 触发延迟 5h21m** | run #148：理论 2026-09-30 13:00 UTC → 实际 created 18:21:10 UTC | 已证实（a 类：GitHub schedule 延迟）；排队 0 秒，非 b/c/d 类 |
| 2 | **Review schedule 触发延迟 3h10m** | run #124：理论 2026-09-30 22:00 UTC → 实际 created 2026-10-01 01:10:15 UTC | 已证实（a 类）；排队 0 秒 |
| 3 | **Scan 2026-10-01 触发点截至审计时刻缺席** | 理论 13:00 UTC，审计 18:32 UTC，已过 332.7 分钟；复查 Scan 最新 run 仍为 2026-09-30 18:21 | **事实已证实，成因无法证明**（可能仍在延迟队列，也可能本次未触发）——需继续观察，不作因果结论 |
| 4 | **Evolve 从未出现 schedule 触发（0/13）** | 全量 13 次 run 事件分布：`workflow_dispatch` × 13，`schedule` × 0 | 已证实；**成因是时间未到**（schedule 引入后首个周六 2026-10-03 尚未到来），**非配置故障** |
| 5 | Scan 注释与实际 cron 分钟数不一致 | `scan.yml` 注释写 "Mon-Fri 21:00 Beijing"，实际 cron `7 13` = 北京 21:07 | 已证实；属**注释未同步**（`7724e03` 刻意避开整点后未更新注释），**非功能错误** |

### 已核查但**未发现**问题的项

| 检查项 | 结论 |
| --- | --- |
| cron 写法错误 | ❌ 未发现。三个 cron 均为合法 5 字段表达式 |
| 时区理解错误 | ❌ 未发现。当前三 workflow 均用显式 UTC（`dd11d91` 已修正早期 `timezone` 误用）；UTC/北京/洛杉矶换算与注释一致 |
| 重复触发（同一触发点多个 run） | ❌ 未发现。Scan/Review 各有 concurrency group 防护 |
| schedule + push 导致双跑 | ❌ 不存在。三个 workflow **均无 push 触发** |
| workflow_dispatch 与 schedule 混淆 | ❌ 未发现。API `event` 字段清晰区分；本报告已按 event 分别统计 |
| 长时间 queued | ❌ 未发现。两个 schedule run 的 `created_at == run_started_at` |
| cancelled 状态 | ❌ 未发现任何 `cancelled` run |
| schedule run 失败 | ❌ 未发现。Scan/Review 各自唯一的 schedule run 均 `success` |
| workflow 被禁用 | ❌ 未发现。三个 workflow state 均为 `active` |

### 关于 failure 的说明（非 schedule 相关）

最近 10 次中存在 3 次 **failure**，但**全部为 `workflow_dispatch`**，与 schedule 无关：

- Scan #142（2026-09-28T13:55:06Z）
- Scan #139（2026-09-24T13:45:14Z）
- Review #115（2026-09-30T04:00:24Z）

---

## E. 结论

### Scan — **存在问题**

- **已证实**：唯一 schedule run（#148）触发延迟 **5h21m**，且延迟全部来自 GitHub schedule 侧（排队 0 秒）。
- **已证实（事实）**：2026-10-01 的触发点截至审计时刻（已过理论时间 5h33m）**未出现**。
- **证据不足部分**：仅 1 次 schedule 样本，无法判定"10/01 缺席"是持续性问题还是单次延迟；其成因无法证明。
- cron 配置本身正确（`7 13 * * 1-5` = 北京周一~周五 21:07）。

### Review — **正常**

- cron 配置正确（`0 22 * * 1-5` = 北京周二~周六 06:00），与注释一致。
- 唯一已过的理论触发点（2026-09-30 22:00 UTC）**已成功触发并 success**。
- 存在 **3h10m** 的 GitHub schedule 平台延迟，属 GitHub Actions 已知的 scheduled run 延迟现象；排队 0 秒、内部耗时 2.5 分钟，无异常。
- 下一个触发点（2026-10-01 22:00 UTC）在审计时刻尚未到达。

### Evolve — **尚未发生首次 schedule**

- cron `0 2 * * 6` = 每周六 UTC 02:00 = 北京周六 10:00 = 洛杉矶周五 19:00。
- schedule 于 `61de4fc`（2026-09-29 14:34 UTC）引入；引入后**首个周六为 2026-10-03**，其 UTC 触发窗口为 **2026-10-03 02:00**，距审计时刻还有 **31.5 小时**。
- 全量 13 次 run 中 **0 次 schedule**，与该时间线完全吻合，**属"尚未发生"而非故障**。
- 2026-10-03 为 10 月第一个周六（北京 day-of-month = 3 ≤ 7），届时 workflow 内的 first-Saturday 检查会通过、业务会执行。
- 本次审计**未手动 dispatch 代替验证**；建议在 2026-10-03 10:00（北京时间）之后复查是否出现 `event=schedule` 的 run。

---

## 审计边界声明

- 本次为**只读审计**：未修改任何文件、未 commit、未 push、未手动触发任何 workflow。
- 所有时间计算基于 GitHub Actions API 返回的 UTC 时间戳；洛杉矶时间按夏令时 PDT（UTC-7）换算，北京时间为 UTC+8。
- 凡无法由现有数据证明的成因（如 runner 启动耗时、10/01 缺席的具体原因），均标注为**无法证明**，未作因果推断。
