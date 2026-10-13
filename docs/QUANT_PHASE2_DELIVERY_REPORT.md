# Quant Research Phase 2 交付报告：Factor Backtest Framework

> 交付时间：2026-10-07 · commit `fdfc3dd` · 状态：已 push，`HEAD == origin/main` ✅

## 0. 只读审计结论（实施前）

| 项 | 审计结果 |
|---|---|
| Snapshot 唯一键 | ✅ `Scan_Date + Ticker`（Phase 1 已固化） |
| Snapshot 是否已产生 | ❌ **远端尚无 `quant_factor_snapshot.csv`**（Phase 1 部署后 Scan 尚未运行，cron 13:07 UTC 未到） |
| OHLC 持久化缓存 | ❌ 仓库无任何持久化 OHLC/价格缓存（`get_kline_data` 每次实时下载即弃） |
| 未来数据 | ✅ Phase 1 snapshot 只含 T 日已确定因子，无未来数据 |

**关键结论**：Snapshot 尚无真实数据 + 无价格缓存 → Phase 2 的正确交付是"**纯函数回测框架 + 完整测试**"，Forward Return 价格作为可注入依赖（`price_map`），数据不足时明确输出 `NOT_ENOUGH_DATA`，绝不做历史回填、绝不擅自设计新的高频抓取系统。

## 1. 修改文件

**无**（零修改）。

## 2. 新增文件（2 个）

| 文件 | 作用 |
|---|---|
| `quant_factor_backtest.py` | 纯研究回测框架：Forward Return 计算 + 五分位 + 因子×Horizon 汇总 + Regime 分层 + 相关/样本量标签 + 可选价格加载器 + 主入口 |
| `tests/test_quant_factor_backtest.py` | 33 项纯函数测试（不依赖 Yahoo 网络） |

## 3. 5D/10D/20D 当前成熟样本

| Horizon | 成熟样本 |
|---|---|
| 5D | **0**（NOT_ENOUGH_DATA） |
| 10D | **0**（NOT_ENOUGH_DATA） |
| 20D | **0**（NOT_ENOUGH_DATA） |

原因：`quant_factor_snapshot.csv` 尚未产生（Phase 1 后 Scan 未运行），且仓库无持久化价格历史。**未做任何历史回填**。

## 4-6. 各因子 N / 可观察 / Not Enough Data

当前所有因子 N=0。框架已内置 `sample_size_label()` 门槛：`N<30` → Exploratory Only、`N<50` → Weak Evidence、`N>=50` → Observable Trend、`N>=100` → Formal Comparison OK。待 snapshot 积累后自动套用。

## 7. 是否历史回填

❌ **否**。零历史回填，零补造历史因子。

## 8. 是否增加网络请求

❌ **否**。框架默认纯函数运行，不触发任何网络请求。`load_price_history()` 价格加载器为**可选**、仅在 snapshot 非空且显式调用时运行，且一次性批量下载（绝不逐 stock × horizon 重复请求）。当前主入口在无价格数据时直接报告缺口，不擅自抓取。

## 9. AI Token 是否增加

❌ **否**。AI Calls = 0，未修改任何 Prompt，未增加 ClawSocket 调用。

## 10. Scan 推荐是否完全一致

✅ **完全一致**。零修改 scan.py / review.py / portfolio_50000.py / dashboard_export.py / app.js / index.html / strategy_params.json / 各 workflow。红线文件逐个核对全部未触碰。

## 11. 测试结果

| 项 | 结果 |
|---|---|
| 新增 Backtest 测试 | **33 / 33 PASS** |
| **全量项目测试** | **372 / 372 PASS**（含 Phase 1 的 30 + 本次 33） |
| py_compile（3.12） | ✅ PASS |
| git diff --check | ✅ PASS |
| 确定性复跑（3 次） | ✅ 输出逐字节一致（无随机性） |
| Snapshot 不被修改 | ✅ 测试覆盖 |

## 12-13. Git 状态

| 项 | 值 |
|---|---|
| commit SHA | `fdfc3dd16c1508c0f2c278e29838d85892f02d55` |
| push | ✅ 成功（无 force） |
| HEAD == origin/main | ✅ **TRUE** |

## 14. 未解决问题（如实上报）

1. **Snapshot 尚未积累数据**：这是数据成熟度问题，非缺陷。回测框架已就绪，等待 Scan 自然运行产生 snapshot。今晚 13:07 UTC Scan 后 `quant_factor_snapshot.csv` 将出现第一批数据，但 Forward Return 需要 T+5/T+10/T+20 的后续交易日，**5D 最早需 5 个交易日后、20D 需 20 个交易日后**才有意义。
2. **价格数据源缺口**：仓库无持久化 OHLC 缓存。框架已提供 `load_price_history()` 批量加载器（一次性下载），但**尚未接入 workflow**——按任务约束"如现有历史价格数据不足先建框架报告缺口，不擅自设计高频抓取"，未在 scan.yml 增加自动抓取。待 snapshot 积累 + 你确认后，再决定是否接入定期的价格批量下载以计算 Forward Return。

## 框架能力清单（已实现、可测试）

- `forward_return_nd()` / `compute_forward_returns()`：T 日之后第 N 个交易日的前瞻收益，未来不存在 → None（不填 0/均值/最近值）
- `compute_factor_summary()`：Factor × Horizon 的 N/WinRate/Avg/Median/Std/Pos/Neg，并标记 Factor_Type（Raw Factor / Composite / Existing Scan Score）
- `compute_quantile_stats()`：横截面五分位（同值安全、样本不足不强行分组、可按日分组避免跨日漂移）
- `compute_regime_summary()`：NORMAL/STRESSED/PANIC 分层
- `compute_correlation()`：Pearson + Spearman（辅助，不作为有效性唯一依据）
- `sample_size_label()`：样本量门槛标签
- `maturity_status()`：数据成熟度判断
- `run_backtest()`：主入口，空数据/缺价格 → 明确 NOT_ENOUGH_DATA

**Phase 2 目标达成**：建立干净、无 Look-Ahead、无 Selection Bias、确定性、可持续积累数据的 Factor Research 基础设施。**未据此修改任何交易策略**（样本为 0，且 Phase 2 定位是研究/测量层）。
