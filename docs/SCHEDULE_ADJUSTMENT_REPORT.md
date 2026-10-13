# Schedule 调整报告（review / evolve 离开整点）

> 生成时间：2026-10-08 00:06 GMT+8
> 铁律：**判决前不 push**。本改动仅本地 commit，origin/main 的 scan cron 仍为 `7 13 * * 1-5`（13:07 UTC），10-08 判决路径不受影响。

---

## 1. 三个 workflow 的 cron 前后对照表

| workflow | 当前 cron（UTC） | 北京时间 | 是否整点 | 新 cron（UTC） | 改后分钟 |
|---|---|---|---|---|---|
| **scan** | `7 13 * * 1-5` | 21:07（工作日） | 否（已避开） | **不动** | 13（质数，已安全） |
| **review** | `0 22 * * 1-5` | 06:00（周二~周六） | **是（整点）** | `23 22 * * 1-5` | 23（质数） |
| **evolve** | `0 2 * * 6` | 10:37（每月首周六） | **是（整点）** | `37 2 * * 6` | 37（质数） |
| dashboard-data（参考，不动） | `*/15 * * * 1-5` | 全天每 15 分钟 | 网格 | 不动 | 0/15/30/45 |

> ⚠️ **一处与原始指令的偏差（已主动修正并需你知晓）**：你给的 review 目标是 `23 22 * * *`（每日），但文件里实际是 `0 22 * * 1-5`（**工作日** `1-5`，注释明确"Tue-Sat 06:00 Beijing = Mon-Fri 22:00 UTC"）。你的意图是"避开整点拥堵"，只动分钟，**不应扩大执行频率**，故我保留 `1-5`，产出 `23 22 * * 1-5`。若你确实要改每日，说一声我改。
>
> evolve 的实际值 `0 2 * * 6` 与你的指令一致，直接改分钟即可。

---

## 2. 改动理由（整点拥堵证据）

- **review（原 `0 22 * * 1-5`）**：位于 `:00` 整点，正是 GitHub 全球调度高峰。历史观测记录显示 review 曾出现 **3h10m 延迟**（见 SCAN_SCHEDULE_INVESTIGATION.md 的整点延迟证据），整点是元凶。改到 `22:23` 离开整点。
- **evolve（原 `0 2 * * 6`）**：同样 `:00` 整点，且历史记录显示其 schedule **从未触发**（疑似整点拥堵 + 首周六条件叠加）。改到 `02:37` 离开整点。
- **避开原则**：① 避开所有 `0/15/30/45` 网格点（dashboard-data 的 `*/15` 占用）；② 避开 `:00` 整点高峰；③ 用质数分钟（23、37）降低与其他仓库 cron 的谐波重叠概率。

---

## 3. 为什么不改 scan

`scan.yml` 的 `7 13 * * 1-5` **已经是正确的写法**：

- 分钟 `7` 是质数，不在 `0/15/30/45` 网格上；
- 不在 `:00` 整点；
- 你原提议的 `20:30`（UTC 12:30）反而会撞 dashboard-data 的 `*/15` 网格（:30），**更糟**。

scan 是 10-08 判决的唯一数据来源（13:07 UTC 触发 → 约 13:32 落 snapshot），动它等于动判决本身，故**坚决不动**。

---

## 4. 为什么不现在 push（判决依赖）

10-08 的 Scan **从 `origin/main` 读取 workflow 文件**。若现在把任何改动 push 到 main：

- push scan 相关改动 → 10-08 scan 会在新时间触发（或不触发）→ 监控器 PID 536931 按 13:07 窗口等 → 等不到 → **误判 DEEPER/OTHER → 判决直接废掉**；
- 即便只 push review/evolve（不碰 scan），也应**等判决后统一推**：保持 `origin/main` 与"判决观测窗口"完全一致，避免任何意外干扰。

本次已 commit 但**未 push**，本地改动停留在工作链顶端，不进入 `origin/main`，运行中的 Scan 仍读旧的 scan cron。

---

## 5. 判决后 push 的顺序建议

判决落定（OK / SYSTEMATIC / DEEPER / OTHER 任一）后，建议**分两次 push**，隔离风险：

1. **先 push cron 改动**（本次 commit `3ed1495`，独立、只动 review/evolve 两行 cron）。
   - 若 cron 改动有问题，可单独 revert，不影响 quant 改动。
2. **再 push 6 个 quant commit**（先 `git rebase origin/main` 到最新，预计干净——两边文件零重叠：一边 `dashboard/data/*`，一边 `quant_*.py`/`scan.py`/`tests/*`）。
   - 其中契约告警 `efc23bf` + Phase3–7 五个测试 commit（见 `/tmp/pre_1008_commits.txt`）。

> 若判决为 **DEEPER / OTHER**：按 Playbook 分支 C，**永不 push**，停下只报告，等你的下一步指令。

---

## 6. git diff --stat

```
 .github/workflows/evolve.yml | 2 +-
 .github/workflows/review.yml  | 2 +-
 2 files changed, 2 insertions(+), 2 deletions(-)
```

**精确 diff：**

```diff
# .github/workflows/review.yml
-    - cron: '0 22 * * 1-5'
+    - cron: '23 22 * * 1-5'

# .github/workflows/evolve.yml
-    - cron: '0 2 * * 6'
+    - cron: '37 2 * * 6'
```

每文件**仅改一行** `- cron:`，`concurrency` / `jobs` / `steps` 全部保持原样（未触碰）。

---

## 7. 新 commit SHA

| 项 | 值 |
|---|---|
| 新 commit | `3ed1495` |
| message | `chore(ci): move review/evolve schedule off the hour` |
| 改动文件 | `.github/workflows/review.yml`、`.github/workflows/evolve.yml` |
| 是否 push | **否**（仅本地 commit） |

> 说明：本 commit 是 pre-1008 那 6 个 quant commit（末位 `fedf63d`）**之后**的第 7 个，二者分离，符合"判决后分两次 push"的设计。`/tmp/pre_1008_commits.txt` 中的 6 个 SHA 不受影响、仍然有效。

---

## 验证结论（第三件）

- ✅ YAML 语法：review.yml / evolve.yml 均 `yaml.safe_load` 通过，cron 正确读取为新值。
- ✅ cron 合法性：两个表达式均为 5 字段，无语法错误。
- ✅ 避撞：新分钟 23 / 37 均不在 `0/15/30/45` 网格，且非 `:00` 整点。
- ✅ git diff：仅 2 文件各 1 行，无多余改动。

**未触碰**：scan 的 cron、任何非 cron 配置、监控 PID 536931、`/tmp/scan_1008_monitor.log`、任何代码/quant 模块、workflow 的 concurrency/jobs/steps。
