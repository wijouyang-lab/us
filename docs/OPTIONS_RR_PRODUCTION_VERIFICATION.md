# Options RR 改造 — 生产验收（只读）

> 性质：**只读验收**。未修改任何代码、CSV 历史数据或其他模块；未 commit、未 push。
> 验收时刻：UTC 2026-10-02 00:03（北京 2026-10-02 08:03）

---

## 0. 验收前置结论：真实生产验收**无法执行**（客观阻塞）

| 阻塞项 | 事实 |
| --- | --- |
| 改造代码是否部署到远端？ | ❌ **否**。工作区改动未 commit、未 push；远端 HEAD 为 `51366b2`，不含期权 RR 改造 |
| 下一次 Scan 是否已发生？ | ❌ **未发生**。cron `7 13 * * 1-5` → 下一次触发点 **2026-10-02 13:07 UTC**（北京 21:07），距验收时刻 **13.06 小时** |
| 自上次 Scan 后有无新 run？ | ❌ 无。最新 Scan 仍为 `#148`（2026-09-30 18:21 UTC，schedule） |
| 远端是否曾运行新代码？ | ❌ **否**。远端 `option_strategies.csv` 为 **56 列、无 `Reject_Reason` 列**（新代码会追加该列） |

> 由于本次任务禁止 commit / push，GitHub Actions **永远只能运行旧代码**，
> 因此"下一次真实 Scan 产出的数据"不会包含本次改造行为。真实生产验收在当前约束下不可达。

**替代做法**：取**远端真实生产数据**（`origin/main:option_strategies.csv`，10 条）作为输入，
用**本地新逻辑**做**只读离线推演**（不写回、不改任何文件），验证新规则对真实数据的判定行为。

---

## 1. 真实生产数据逐条推演（远端 CSV + 本地新逻辑）

| Ticker | Strategy | MaxProfit | MaxLoss | raw RR | 新 Status | Reject_Reason |
| --- | --- | --- | --- | --- | --- | --- |
| FTNT | CALL_DEBIT_SPREAD | 548.0 | 452.0 | 1.212389 | **Rejected** | Reward/Risk below 2.0 |
| ALL | SHORT_PUT | 370.0 | 20630.0 | **0.017935** | **Rejected** | Reward/Risk below 2.0 |
| PAYX | CALL_DEBIT_SPREAD | 295.0 | 205.0 | 1.439024 | **Rejected** | Reward/Risk below 2.0 |
| APA | CALL_DEBIT_SPREAD | 145.0 | 105.0 | 1.380952 | **Rejected** | Reward/Risk below 2.0 |
| SCHW | CALL_DEBIT_SPREAD | 441.0 | 309.0 | 1.427184 | **Rejected** | Reward/Risk below 2.0 |
| MPC | CALL_DEBIT_SPREAD | 1100.0 | 900.0 | 1.222222 | **Rejected** | Reward/Risk below 2.0 |
| CBOE | SHORT_PUT | 570.0 | 23430.0 | 0.024328 | **Rejected** | Reward/Risk below 2.0 |
| NTAP | SHORT_PUT | 650.0 | 18350.0 | 0.035422 | **Rejected** | Reward/Risk below 2.0 |
| TER | SHORT_PUT | 2170.0 | 33830.0 | 0.064144 | **Rejected** | Reward/Risk below 2.0 |
| ALL | SHORT_PUT | 380.0 | 20620.0 | 0.018429 | **Rejected** | Reward/Risk below 2.0 |

> gating 全程使用 **raw 浮点值**（未四舍五入）。

---

## 2. 逐条验收检查

| # | 检查项 | 结果 |
| --- | --- | --- |
| 1 | 所有 `Status=Active` 的 `RewardRisk >= 2.0`（raw 判定） | ✅ 通过（Active 数为 0，无违例） |
| 2 | 所有 `RR < 2.0` 必须 Rejected 且有合理 Reject_Reason | ✅ 通过（10/10 均为 `Reward/Risk below 2.0`） |
| 3 | RR unavailable / None / NaN 不得为 Active | ✅ 通过（无 RR unavailable 记录，亦无此类 Active） |
| 4 | 用户 SHORT PUT 示例（210 / 3.70 / 370 / 20630 / raw ≈0.017935）必须 Rejected | ✅ 通过（实测 raw = 0.017935 → Rejected） |
| 5 | Dashboard Actionable 只含 Active；Rejected 保留底层但不进 Actionable | ✅ 通过（见第 3 节） |
| 6 | Review：Rejected 不得作为新的 Active Option Position | ✅ 新数据通过（Status="Rejected" 不匹配 Active 过滤）；⚠️ 历史旧数据见第 4 节 |
| 7 | Email：Rejected 不得进入最终推荐 | ✅ 新数据通过；⚠️ 历史旧数据见第 4 节 |
| 8 | 本次验证未修改任何代码 / CSV / 其他模块 | ✅ 通过（见第 5 节） |

---

## 3. Dashboard 验证（真实 CSV 输入）

| 项 | 结果 |
| --- | --- |
| `build_options` 解析条数 | **10**（Rejected / 旧记录全部保留在底层，未删除） |
| `is_actionable_option` 过滤后 Actionable | **0 条** |
| rejected 统计 | **10 条** |

> 说明：真实 CSV 中 SHORT_PUT 的 `RewardRisk` 为空（旧代码从不计算），
> CALL_DEBIT_SPREAD 为 1.222–1.439。两者均不满足 `Status=Active 且 RR>=2.0`，故全部不可 Actionable。
> **Dashboard 已能正确屏蔽这批 RR<2.0 的历史数据。**

---

## 4. Review / Email 验证（真实 CSV 输入）

| 端 | 过滤条件 | 真实 CSV 结果 |
| --- | --- | --- |
| **Review** | `Status == "Active"`（review.py line 918） | 10 条全部匹配 → 会被视为 Active 持仓 |
| **Email** | `Status == "Active"`（get_recent_option_recommendations） | 返回 10 条 |

### ⚠️ 报告的问题（不自行修改）

**问题**：Review 与 Email 仅按 `Status` 字段过滤，**未做 Reward/Risk 校验**。
因此远端**历史遗留记录**（`Status=Active` 但 RR 为 0.018–1.44）仍会进入 Review 持仓与 Email 推荐，
与 Dashboard（已按 RR 屏蔽）**不一致**。

| 数据类型 | Dashboard | Review | Email |
| --- | --- | --- | --- |
| 新生成的 `Status="Rejected"` | ✅ 屏蔽 | ✅ 屏蔽 | ✅ 屏蔽 |
| 历史遗留 `Status="Active"`（RR<2.0） | ✅ 屏蔽 | ⚠️ **未屏蔽** | ⚠️ **未屏蔽** |

**成因**：远端 CSV 为旧代码产出，`Status` 尚未被重写；本次任务明确禁止修改历史 CSV，
也禁止修改 review.py / scan.py（两者原有过滤逻辑正确，属最小改动范围）。

**预期消除时机**：下一次 Scan 使用新代码重新生成后，这些记录会变为 `Status="Rejected"`，
三端即恢复一致。**无需改代码**，仅待数据重新生成。

---

## 5. 只读性校验

| 项 | 结果 |
| --- | --- |
| `git status --short` | 仅 3 个已改业务文件 + 1 个新增测试（与改造后一致，**无新增修改**） |
| `git diff --stat -- option_strategies.csv .github/ scan.py review.py dashboard/fetch_runtimes.py` | **无输出**（均未改动） |
| HEAD | `5d65f84`（未变，未 commit） |
| 远端 CSV md5 比对 | `5168c54a3f448be3200b23f9c8c18dee`（本地读取与远端一致，**未被改写**） |
| tracked `.pyc` | 8 个完整，未删除 |

---

## 6. 最终输出

| 统计项 | 值 |
| --- | --- |
| **Options 总数** | **10** |
| **Active 数** | **0** |
| **Rejected 数** | **10** |
| **RR unavailable 数** | **0** |
| **最低 / 最高 Active RR** | **N/A**（无 Active 记录） |
| **是否发现 <2.0 的 Active** | **否** ✅ |
| **是否发现 RR unavailable 的 Active** | **否** ✅ |
| **Dashboard / Review / Email 是否一致** | **新数据：一致 ✅；历史遗留旧数据：不一致 ⚠️**（Dashboard 已屏蔽，Review/Email 未屏蔽 —— 待下次 Scan 重算后自动消除） |

---

## 结论

**PRODUCTION VERIFICATION BLOCKED（真实生产验收阻塞）**

阻塞原因：改造代码未 commit/push，GitHub Actions 仍运行旧逻辑；下一次 Scan 触发点在 13 小时后且同样只会用旧代码。在禁止 commit 的约束下，真实生产数据无法产出。

**已完成的替代验证**：以远端真实生产数据（10 条）为输入，用本地新逻辑做只读离线推演，
结果满足全部业务规则（0 个 Active、10 个 Rejected、无 <2.0 的 Active、无 unavailable 的 Active、
用户 210 PUT 案例正确 Rejected）。

**已发现问题（仅报告，未修改）**：Review 与 Email 对历史遗留 `Status=Active` 且 RR<2.0 的旧记录未做 RR 校验，
与 Dashboard 不一致；该问题会在下一次 Scan 用新代码重算 CSV 后自动消除，无需代码改动。

**建议（待你决定）**：如需真正完成生产验收，需先 commit + push 改造，再等待一次 Scan（最近窗口为 2026-10-02 13:07 UTC）。
