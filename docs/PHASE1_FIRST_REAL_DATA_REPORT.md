# Quant Phase 1 · 首份真实生产数据验证报告

> **里程碑**：`quant_factor_snapshot.csv` 首次由真实生产 Scan 生成
> **Scan 提交**：`d030f0fb`（2026-10-07 13:32:03 UTC）`chore: persist scan pending and AI snapshots`
> **验证时间**：2026-10-07 14:01 UTC
> **结论**：✅ **28 PASS / 1 WARN（已证伪）/ 0 FAIL**

---

## 1. 落盘证据

| 项 | 值 |
|---|---|
| 生成提交 | `d030f0fb` @ 13:32:03 UTC（Scan 触发 13:07，耗时 ~25 min） |
| 完整路径 | 远端仓库根目录 `quant_factor_snapshot.csv` |
| blob 大小 | 61,879 字节 |
| 总行数 | 263（表头 1 + 数据 262） |
| **列数** | **34**（改动前 33，新增 `schema_version` 后 34） |
| Scan_Date | `2026-10-07`（262/262） |
| Technical_Date | `2026-10-05`（262/262） |
| Ticker 数 | 262 |
| **schema_version** | **`phase1.v1`（262/262）✅** |

> **push 赶在 Scan 之前生效** —— 首份 snapshot 即携带 `schema_version`，无需事后补。

同批落盘的还有 **`quant_factor_price_history.csv`**（Phase 2B，2,096 行）—— Phase 1 与 2B 双双首次产出。

---

## 2. 15 项核验结果

| # | 项目 | 结果 |
|---|---|---|
| 1 | snapshot 是否生成 | ✅ |
| 2 | 生产路径正确（远端仓库根目录） | ✅ |
| 3 | Scan_Date = 本次日期 `2026-10-07` | ✅ |
| 4 | Ticker 数 262 ∈ [150,300] | ✅ |
| 5 | 覆盖完整 snapshot_pool（**含 184 条 Gate 未通过项**） | ✅ |
| 6 | Gate_Status 填充率 100% | ✅ |
| 7 | 8 个 Quant Factor 列齐全 | ✅ |
| 8 | 数值无 NaN / inf；量级合理 | ✅ |
| 9 | 唯一键 `Scan_Date\|Ticker` 无重复 | ✅ |
| 10 | 精度 ≤4 位小数；Price 2 位 | ✅ |
| 11 | Dashboard 已同步（snapshot_rows=262） | ✅ |
| 12 | Quant 状态 `NOT_ENOUGH_DATA` → `DATA_AVAILABLE` | ✅ |
| 13 | Dashboard 其它数据未被破坏 | ✅（详见第 4 节） |
| 14 | Scan workflow 成功完成 | ✅（有提交产物） |
| 15 | R8（Scan 成功但无 snapshot） | **未触发** ✅ |

---

## 3. Gate_Status 分布（关键：证明无 selection bias）

```
PASS_PRE_AI        78
QUANT_FAIL         83
TECH_FAIL          66
SECTOR_RS_FAIL     18
EVENT_HARD_AVOID   17
─────────────────────
合计              262
```

**184 条未通过项被完整保留** —— 证实 `snapshot_pool` 取的是**进入 Gate 的全候选池**，而非仅通过者。这正是当初设计要避免的选择性偏差。

---

## 4. Factor 数值健康度（262 行 × 8 因子）

| 因子 | 有效 | 取值范围 | 判定 |
|---|---|---|---|
| Momentum_5D_Pct | 262/262 | [-82.14, 40.30] | ✅ |
| Momentum_20D_Pct | 262/262 | [-83.81, 44.83] | ✅ |
| Momentum_60D_Pct | 262/262 | [-83.84, 179.70] | ✅ |
| Realized_Volatility_20D_Pct | 262/262 | [10.97, 302.50] | ✅ |
| Volume_Ratio_20D | 262/262 | [0.4206, 4.354] | ✅ |
| ZScore_20D | 262/262 | [-3.877, 4.892] | ✅ |
| Beta_60D_SPY | 262/262 | [-1.255, 4.070] | ✅ |
| Stock_RS_20D_vs_SPY | 262/262 | [-85.77, 42.86] | ✅ |

- **空值率 0.0%**（8 因子全部 262/262 有值）
- **无 NaN / inf / 不可解析值**
- 精度全部 ≤4 位小数，`Price` 2 位 —— **无浮点尾数污染**
- `Technical_Date > Scan_Date` 的异常行 = **0**（无未来日期）

---

## 5. 唯一告警及其证伪

验证脚本报出 1 条 WARN：

```
stocks  基准=34 → 当前=42
Core 13 → 16    Observation 21 → 26
```

**已证伪 —— 非 Quant 接入破坏。** 差集核对：

```
新增: CNP, ED, FANG, HWM, LUV, NRG, WM, WRB   （8 只）
移除: （无）
```

这 8 只**完全等于**今日 `us_stocks_pending_20261007.csv` 的 8 个 ticker。即 Dashboard 股票池由 34 → 42 是 **Scan 正常产生新推荐** 的结果，与 Quant 接入无关。

其余数据全部一致：

| 数据 | 基准 → 当前 |
|---|---|
| review.records | 391 → 391 ✅ |
| history | 46 → 46 ✅ |
| options | 0 → 0 ✅ |
| runtimes | 3 → 3 ✅ |
| portfolio 键集合 | 一致（17 键）✅ |

---

## 6. Dashboard 状态转换

```
quant.status                  = RESEARCH
quant.data_availability       = NOT_ENOUGH_DATA  →  PARTIAL
quant.factor_lab.status       = NOT_ENOUGH_DATA  →  DATA_AVAILABLE
quant.factor_lab.snapshot_rows = 0               →  262
```

Dashboard 已正确感知首份真实数据，且 `snapshot_rows` 与文件行数一致（262）。

---

## 7. 一处需要关注的数据观察（非阻塞）

**`Technical_Date = 2026-10-05`，而 `Scan_Date = 2026-10-07`，相差 2 个自然日。**

但同批产出的 **Phase 2B 价格历史最新日期是 `2026-10-06`** —— 说明 10-06 是有行情数据的交易日，而因子快照停在 10-05。

| 可能原因 | 说明 |
|---|---|
| Yahoo 单股 `period="6mo"` 返回滞后 | Scan 的 `get_kline_data()` 用单股下载；价格历史用批量下载，两者数据源时序可能不同步 |
| 需进一步定位 | 建议下次 Scan 后对比两者日期是否仍差 1 天 |

**影响评估**：
- **不是 look-ahead 问题**（Technical_Date < Scan_Date，无未来数据）✅
- 表现为因子 T 日比可获取数据**滞后 1 个交易日**，属数据新鲜度问题
- 不影响正确性，但会让 Phase 2 的 forward return 基准日同步后移

建议列入 STEP 4–8 的观察项，暂不修改代码。

---

## 8. 监控进程表现

| 项 | 值 |
|---|---|
| PID | 209240 |
| 日志路径 | `/tmp/phase1_scan_monitor.log` |
| 检出轮询 | 第 22 次，13:34:55 UTC |
| 检出后行为 | 自动等待 25 分钟 dashboard 同步 |
| 完成时间 | 14:00:02 UTC |
| 最终状态 | `★ 监控任务完成（已检出 snapshot 并完成 dashboard 同步窗口）` |

---

## 9. 下一步

首份真实数据已落地并通过 15 项核验。**R1–R8 风险均未触发。**

可以进入 **STEP 4–8**（Phase 3/4/5/6/7 各自补测）：

- Phase 2 Backtest 现在具备了 snapshot + price history 两个输入；但 **20D forward return 需等到约 10-29（T+20 交易日）** 才有成熟样本
- Phase 5 Walk-Forward 需 ≥70 个 snapshot 日期（约 14 周），期间合法保持 `NOT_ENOUGH_DATA`

---

*首份真实数据验证报告 · 2026-10-07 14:01 UTC · 未做任何代码改动*
