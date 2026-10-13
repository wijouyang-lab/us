# Quant Research Phase 2B 交付报告：Persistent Price History Layer

> 交付时间：2026-10-07 · commit `9398983` · 状态：已 push，`HEAD == origin/main` ✅

## 0. 只读审计结论（实施前）

### 1. T 日价格实际口径（重点结论）

| 项 | 结论 |
|---|---|
| Phase 1 因子 close[-1] 是否为完整收盘日 | ✅ **是完整收盘日** |
| 依据 | `get_kline_data()` → `_filter_completed_daily_bars()`，剔除未完成 bar |
| Scan 运行时间 | 13:07 UTC = 美东 09:07（盘前，`_last_completed_regular_date_us` 判定 <16:00 → cutoff=昨天） |
| **auto_adjust 口径** | `get_kline_data` 用 `auto_adjust=False`（未复权），snapshot 的 `Price`/所有技术因子都基于它 |
| Snapshot 行 | `Technical_Date` = 最后完整交易日；`Price` = 该日未复权 Close |

**关键**：Phase 1 因子确实使用最后完整交易日收盘价，无未完成 bar 污染。**因此无需停止实施**——Forward Return 的 T 日 = `Technical_Date`，Close[T] = snapshot 的 `Price` 字段（已固定）。价格历史层同样用 `auto_adjust=False`，保证同源同口径。

## 1. 修改文件

| 文件 | 改动 | 说明 |
|---|---|---|
| `.github/workflows/scan.yml` | ① 新增"更新 Quant 价格历史"步骤 ② artifact + git add 加 `quant_factor_price_history.csv` | 仅新增持久化，cron/concurrency/runner/push 架构零改动 |
| `quant_factor_backtest.py` | 新增 `run_backtest_from_history()` 便捷入口（从 price_history CSV 构建 price_map） | 纯新增函数 |

## 2. 新增文件

| 文件 | 作用 |
|---|---|
| `quant_factor_price.py` | 持久化价格层：批量下载 + 幂等 upsert + price_map 构建 + 主入口 |
| `tests/test_quant_factor_price.py` | 25 项纯函数测试 |
| `quant_factor_backtest.py` + `tests/test_quant_factor_backtest.py` | **恢复被误删的 Phase 2 文件**（见第 0.5 节） |

## 0.5. ⚠️ 重要发现：Phase 2 文件曾被误删（已恢复 + 根因已定位）

**事实**：上一阶段交付的 `quant_factor_backtest.py` 和 `tests/test_quant_factor_backtest.py` 被 dashboard-data 自动提交 `b2e1150` **删除**（该提交 parent 是 Phase 2 commit `fdfc3dd`，却把这两个文件标记为 D）。

**根因（已在本地精确复现）**：`dashboard-data.yml` 的 push 重试循环里 `git reset --soft FETCH_HEAD` 后直接 `git commit`，**缺少首次提交才有的"提交范围守卫"**。当 dashboard-data run checkout 了旧 commit（无 backtest 文件）、而我的 backtest commit 在它运行期间被 push 到 main 时：
- 它的 push 被拒 → `git reset --soft FETCH_HEAD`（HEAD 移到含 backtest 的 commit，但工作区仍是旧版）→ staged diff 里 backtest 被标记为 **D（删除）** → commit 后文件从 main 消失。

**处理**：本次已从历史 `fdfc3dd` 恢复这两个文件并重新提交。但 **`dashboard-data.yml` 的这个 bug 未修复**——它超出 Phase 2B 授权范围（禁止事项明确不修改 dashboard-data.yml），需要你确认后另行修复。**风险**：未来任何新文件在 dashboard-data 并发撞车时仍有被误删的可能。

## 3. Price History 当前行数 / Unique Ticker

| 项 | 值 |
|---|---|
| `quant_factor_price_history.csv` 当前行数 | **0**（尚未产生，snapshot 仍为空） |
| Unique Ticker | **0** |

原因：`quant_factor_snapshot.csv` 尚不存在（Phase 1 部署后 Scan 尚未运行）。启动阶段正确行为：Snapshot=0 → Price History 为空 → Backtest=NOT_ENOUGH_DATA，**不做历史回填**。

## 4. 成熟样本 / NOT_ENOUGH_DATA

| Horizon | 成熟样本 |
|---|---|
| 5D | 0 |
| 10D | 0 |
| 20D | 0 |

NOT_ENOUGH_DATA 数量 = 全部（无 snapshot 数据）。5D/10D/20D 将在第一批 snapshot 出现后随时间自然成熟。

## 5-7. 网络请求 / AI / Scan 一致性

| 项 | 结果 |
|---|---|
| 新增网络请求 | **每日最多 1 次批量 `yf.download(tickers)`**（绝不逐 ticker 循环） |
| AI Calls | **0**（未加任何调用/Prompt） |
| Scan 推荐结果改变 | **0**（scan.py 选股逻辑零改动） |
| Quant_Score / Final_Score 改变 | **0** |

## 8. 测试 / 检查

| 项 | 结果 |
|---|---|
| 新增 Price 测试 | **25 / 25 PASS** |
| **全量项目测试** | **397 / 397 PASS**（含 Phase 1 30 + Phase 2 33 + 本次 25） |
| py_compile（3.12） | ✅ PASS |
| git diff --check | ✅ PASS |
| 确定性复跑（3 次） | ✅ 输出逐字节一致 |
| 红线文件 | ✅ scan.py/review.py/portfolio/dashboard/options/strategy_params/dashboard-data.yml/review.yml 全部未触碰 |

## 9-10. Git 状态

| 项 | 值 |
|---|---|
| commit SHA | `939898320472afc9e40988429fb74e205d9089b3` |
| push | ✅ 成功（无 force） |
| HEAD == origin/main | ✅ **TRUE** |

## 11. 未解决问题

1. **🔴 dashboard-data.yml 并发删除 bug（未修复，需授权）**：push 重试循环缺提交范围守卫，已导致 Phase 2 文件被误删一次，未来有复发风险。修复需改 dashboard-data.yml（超出本次授权），建议在重试循环的 `git commit` 前加与首次提交相同的范围守卫。
2. **Snapshot 尚未积累**：Price History 需等 Scan 自然运行产生 snapshot 后才有数据（非缺陷，是数据成熟度）。
3. **价格口径已在报告确认**：Phase 1 用完整交易日未复权收盘，本层严格对齐，无需改口径。

## 测试覆盖对照（任务第十节 15 项）

✅ Date|Ticker 幂等 upsert、✅ 重复不产生重复、✅ 新日期追加、✅ 历史不覆盖、✅ 缺价格→None、✅ T+5/10/20 正确、✅ 周末不误算交易日、✅ 缺失未来→None、✅ 不使用未来因子、✅ 重复运行一致、✅ 空 Snapshot 正常、✅ 全候选池覆盖、✅ Review/Exit 完全不参与。

**Phase 2B 目标达成**：为 Factor Snapshot 提供真实历史价格的能力已建立，Forward Return 口径与 Phase 1 严格一致，可持续积累，无 Look-Ahead、无 Selection Bias、无历史回填。
