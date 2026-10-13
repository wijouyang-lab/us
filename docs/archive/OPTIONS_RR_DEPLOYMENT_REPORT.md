# Options RR 改造 — 部署与生产验收报告

> 部署时刻：UTC 2026-10-02 00:30（北京 08:30）

---

## 1. Commit & Push

| 项目 | 值 |
| --- | --- |
| Commit SHA | `b1c43f8dd41910aa339ec0d1bcf3e1d94c325b3d`（短 `b1c43f8`） |
| Message | `fix(options): enforce 2.0 reward/risk gate for actionable options` |
| 变更 | app.js、dashboard_export.py、scan_us_option_engine.py + 新增 tests/test_options_reward_risk.py（4 files, +509/−6） |
| Push | ✅ 成功（`a8ae290..b1c43f8 main -> main`） |
| 部署确认 | 远端 `scan_us_option_engine.py` 含 `MIN_REWARD_RISK`/`evaluate_trade_eligibility`（8 处）；`dashboard_export.py` 含 `is_actionable_option`（4 处） |

---

## 2. 部署过程中发现并修复的问题（真实问题，已处理）

### 问题：并发提交竞争导致正确数据被旧数据覆盖

我改动 `dashboard_export.py` 触发了 `dashboard-data` workflow（push 事件），但当时一个
`workflow_dispatch`（旧代码 `a8ae290`）正并行运行，两个 run 撞在 `concurrency` 组上。

**日志证据**（push run `36946306585`）：

```
Options 数量 : 0（Active 0）        ← 新代码正确生成了 0 条 Actionable
...
push 被拒绝（疑似并发提交），pull --rebase 后重试 (1/3)
...（重试 3 次均失败）
##[warning]重试后仍无法推送，本次数据将在下一轮定时任务覆盖刷新
```

- 旧代码 run（`36946296514`）在被取消前抢先提交了 `0658e1f`（10 条 Active 的旧逻辑数据）
- 新代码 run 生成的正确数据（0 条 Active）推送时被拒绝，3 次重试失败后**被丢弃**
- 结果：线上曾短暂出现 `options=10`（旧数据）

**修复**：重新 `workflow_dispatch` 触发一次 `dashboard-data`（run `36946596314`），无并发竞争，
新代码正确生成并成功推送 `f24866d`。

> 这**不是**本次 RR 改动的代码缺陷，而是既有的 `concurrency: cancel-in-progress: true` +
> 提交重试机制在极端并发下丢弃了正确数据。**未修改 workflow**（遵循最小改动，且该机制整体可用）。

---

## 3. Dashboard 层生产验收（已通过）

以**真实生产数据**（`option_strategies.csv` 10 条旧记录，Status 全为 Active）为输入，
新 `dashboard_export.py` 的过滤逻辑在真实 GitHub Actions 环境中运行结果：

| 项 | 结果 |
| --- | --- |
| `dashboard_data.json` options[] | **0 条**（正确，无 Actionable） |
| `review.active_options_count` | **0** ✅ |
| `review.rejected_options_count` | **10** ✅ |
| 线上 `app.js` 含 `isActionableOption` | ✅（2 处，已部署） |
| GitHub Pages 部署 | ✅ `built`（commit `f24866d`） |
| 线上 `dashboard_data.json` | ✅ options=0、active=0、rejected=10 |

### 一致性验证

| 端 | 行为 | 状态 |
| --- | --- | --- |
| **Dashboard** | 10 条旧记录（RR 0.018–1.44 或为空）全部被过滤，0 Actionable | ✅ 正确屏蔽 |
| **Review** | 仅按 `Status=="Active"` 过滤（未改，最小改动） | ⚠️ 历史旧记录仍会进入（待 Scan 重算消除） |
| **Email** | 仅按 `Status=="Active"` 过滤（未改） | ⚠️ 历史旧记录仍会进入（待 Scan 重算消除） |

> 按你的要求，Review / Email 保持不修改。三端在**新生成的 Rejected 数据**上是一致的；
> 历史遗留 `Status=Active` 旧记录的差异会在 Scan 重算后自动消除。

---

## 4. Scan 等待状态（剩余验收步骤）

| 项 | 值 |
| --- | --- |
| Scan cron | `7 13 * * 1-5`（UTC） |
| 下一次触发点 | **2026-10-02 13:07 UTC = 北京 21:07**（周五，在 cron 范围内） |
| 距部署时刻 | **约 12.5 小时** |

**待 Scan 完成后需复查**（真实生产验收的最终一步）：

1. `option_strategies.csv` 新增 `Reject_Reason` 列（56 → 57 列）
2. 新生成的记录 `Status` 由 Active 变为 `Rejected`（RR < 2.0）
3. 用户案例 ALL / SHORT_PUT（210 / 3.70）→ `MaxLoss=20630`、`raw RR≈0.0179`、`Status=Rejected`
4. 出现 RR ≥ 2.0 的结构才标记 Active

> 提醒：Stage 6B/6C 已观察到 Scan schedule 存在**延迟（9/30 延迟 321 分钟）甚至缺失（10/01 无 run）**的异常。
> 若 13:07 UTC 后仍未出现 Scan run，则 CSV 重算会进一步推迟，属 schedule 问题，与本次 RR 改造无关。

---

## 5. 只读/范围确认

| 项 | 结果 |
| --- | --- |
| Review / Email | **未修改**（符合要求） |
| Schedule / Runtime / 股票逻辑 / 数据源 / AI | **未修改** |
| 历史 CSV | **未重写**（`git diff -- option_strategies.csv` 无输出） |
| workflow 文件 | **未修改** |

---

## 结论

- ✅ **Commit + Push 完成**（`b1c43f8`，已部署到 `origin/main`）
- ✅ **Dashboard 层生产验收通过**（真实数据 → 0 Actionable / 10 Rejected，线上页面已生效）
- ⏳ **最终验收（CSV 由 Scan 重算为 Rejected）待下一次 Scan**：预期 2026-10-02 13:07 UTC（北京 21:07）

**Deployment 阶段完成，等待 Scan 后做最终数据验收。**
