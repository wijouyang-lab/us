# 每日 Snapshot 字段充足性调查（Phase 2–7）

> 调查性质：**只读**。仅核对 `quant_factor_lab.py` / `quant_factor_price.py` 及 Phase 2–7 各研究层实际读取的列，不改动任何代码、不补采数据。
> 调查时间：2026-10-09
> 涉及文件：`quant_factor_lab.py`、`quant_factor_price.py`、`quant_factor_backtest.py`(P2)、`quant_factor_validation.py`(P3)、`quant_score_v2.py`(P4)、`quant_walk_forward.py`(P5)、`quant_shadow.py`(P6)、`quant_production.py`(P7)

---

## 1. 结论摘要（TL;DR）

| 项 | 结论 |
|----|------|
| Snapshot 列数 | **34 列**（已核对 `SNAPSHOT_COLUMNS`，见 §2） |
| Price history 列 | `Date, Ticker, Close, schema_version`（仅 Close，无 OHLCV） |
| Phase 2（回测） | **够** |
| Phase 3（验证） | **够**（消费 P2 产物） |
| Phase 4（候选模型） | **够**（消费 P3 产物） |
| Phase 5（Walk-Forward） | **够**（消费 P2 产物） |
| Phase 6（Shadow） | **部分够**（缺 `Final_Score`/`Tag` 两列，已优雅降级，不阻断） |
| Phase 7（生产治理） | **够**（只读治理产物，不碰 snapshot/价格） |
| 是否需要补采 OHLCV | **当前不需要**（见 §7，仅列出未来触发方向） |

**核心结论**：当前设计的全部前瞻收益（forward return）严格基于 **Close[T] / Close[T+n]**，价格历史只落 `Close`。Phase 2–7 没有任何一处读取 Open / High / Low / Volume。34 列 snapshot + Close-only 价格历史 **足以支撑 Phase 2–7 的现状实现**。唯一瑕疵是 Phase 6 期望的 `Final_Score`/`Tag` 不在 34 列中（代码已降级处理，不影响运行）。

---

## 2. Snapshot 34 列清单（来自 `quant_factor_lab.py:68-81`）

`SNAPSHOT_COLUMNS` 固定顺序，下游 Backtest 按列名读取。

| # | 列名 | 类别 | Phase 2–7 用途 |
|---|------|------|----------------|
| 1 | `Scan_Date` | 元数据 | 横截面分档/分组键（P2/P5/P6） |
| 2 | `Technical_Date` | 元数据 | T 日（最后完整交易日），前瞻收益定位锚（P2/P5/P6） |
| 3 | `Ticker` | 元数据 | 标的标识 |
| 4 | `Name` | 元数据 | 展示用，P6 输出 |
| 5 | `Sector` | 元数据 | 展示用，P6 输出 |
| 6 | `Price` | 价格 | **= Close[T]**，前瞻收益基准价（P2/P6） |
| 7 | `RSI_14` | Raw 因子 | 因子×Horizon 统计 |
| 8 | `Bias_Pct` | Raw 因子 | 同上 |
| 9 | `MACD_Hist` | Raw 因子 | 同上 |
| 10 | `MA20` | Raw 因子 | 同上 |
| 11 | `MA50` | Raw 因子 | 同上 |
| 12 | `MA20_Slope_5D` | Raw 因子 | 同上 |
| 13 | `ATR_Pct` | Raw 因子 | 同上 |
| 14 | `KDJ_J` | Raw 因子 | 同上 |
| 15 | `Volume_Ratio_5D` | Raw 因子 | 同上 |
| 16 | `Momentum_5D_Pct` | Raw 因子 | 同上 |
| 17 | `Momentum_20D_Pct` | Raw 因子 | 同上 |
| 18 | `Momentum_60D_Pct` | Raw 因子 | 同上 |
| 19 | `Realized_Volatility_20D_Pct` | Raw 因子 | 同上 |
| 20 | `Volume_Ratio_20D` | Raw 因子 | 同上 |
| 21 | `ZScore_20D` | Raw 因子 | 同上 |
| 22 | `Beta_60D_SPY` | Raw 因子 | 同上 |
| 23 | `Stock_RS_20D_vs_SPY` | Raw 因子 | 同上 |
| 24 | `Sector_RS_20D_Pct` | Raw 因子 | 同上 |
| 25 | `VIX` | Raw 因子 | 同上（市场状态代理） |
| 26 | `Market_Regime` | 上下文 | Regime 分层（P2/P5/P6），**非因子但被读取** |
| 27 | `Fundamental_Score` | Existing 分数 | 因子×Horizon 统计 |
| 28 | `Event_Score` | Existing 分数 | 同上 |
| 29 | `Technical_Score_25` | Existing 分数 | 同上 |
| 30 | `Risk_Liquidity_Score` | Existing 分数 | 同上 |
| 31 | `Quant_Score` | 复合分数 | 基准模型（P5）、Existing 选择（P6） |
| 32 | `技术确认数` | 元数据 | 仅落盘，未被 Phase 2–7 分析 |
| 33 | `Gate_Status` | 元数据 | 仅落盘，未被 Phase 2–7 分析 |
| 34 | `schema_version` | 版本 | 版本校验（`phase1.v1`） |

**因子覆盖**：Raw 因子 19 个 + Existing 分数 4 个 + 复合 `Quant_Score` 1 个 = **24 个因子列**；外加 `Price`、`Market_Regime` 2 个价格/状态列；其余 8 列为元数据/版本。

---

## 3. Price history schema（来自 `quant_factor_price.py:39`）

```python
PRICE_HISTORY_COLUMNS = ["Date", "Ticker", "Close", "schema_version"]
```

- 唯一键：`Date | Ticker`（幂等 upsert，历史不覆盖）
- **只存收盘价 Close**，不存 Open / High / Low / Volume。
- 口径：`auto_adjust=False`（未复权）+ 仅完整交易日（`filter_completed_daily_bars`），与 Snapshot 的 `Price` 同源同口径（`quant_factor_price.py:10-16`）。

> 这是整条链路“不需要 OHLCV”的根因：前瞻收益的定义从一开始就锁定在 **Close[T] → Close[T+n]**（`quant_factor_backtest.py:27-32`）。

---

## 4. 各 Phase 实际读取的列

### Phase 2 — `quant_factor_backtest.py`（因子前瞻收益）
**读哪些列**：
- Snapshot：`Ticker`、`Technical_Date`、`Price`（=Close[T]）、`Snapshot_Date`（分组）、`Market_Regime`（Regime 分层）
- Snapshot 因子：`ALL_FACTORS` = 19 Raw + `Quant_Score` + 4 Existing 分数（定义见 `:51-60`）
- Price history：`Date, Ticker, Close`（构造 `price_map` → `forward_return_nd`）
- **Forward return 算法**（`:89-116`）：`Close[T之后第n交易日] / Close[T] - 1`，n ∈ {5,10,20}。**只用到 Close，未来交易日缺失→None（不填 0/插值）**。
- 是否用 Open/High/Low/Volume：**否**。

### Phase 3 — `quant_factor_validation.py`（因子有效性验证）
**读哪些列**：只读 Phase 2 产物 `quant_factor_backtest.csv`，消费其中：
- 各因子列 + `Forward_Return_ND` + `Technical_Date`（时间稳定性切段）+ `Market_Regime`（Regime 分层）
- 不读 snapshot，不读 price history，不用 OHLCV。

### Phase 4 — `quant_score_v2.py`（候选模型研究）
**读哪些列**：只读 Phase 3 产物 `quant_factor_validation.csv`、`quant_factor_correlation.csv`。
- `FACTOR_REGISTRY_DEF`（`:78-104`）静态定义因子→分组映射，因子名全部来自 snapshot 34 列；
- 不读任何原始价格/OHLCV，不做任何参数拟合（权重留待 P5）。

### Phase 5 — `quant_walk_forward.py`（OOS / Walk-Forward）
**读哪些列**：只读 Phase 2 产物 `quant_factor_backtest.csv`：
- `Technical_Date`（时间窗口切分，严格不 shuffle，`:334-338`）
- `RAW_FACTORS`（frozen winsorized z-score 归一化 + 模型打分，`:362-373`）
- `Quant_Score`（基准模型，`:190-194`）
- `Forward_Return_ND`（OOS 评估，`:205`）
- `Market_Regime`（Regime 稳定性，`:404-412`）
- 是否用 OHLCV：**否**（前瞻收益已由 P2 算好，本层只评价）。

### Phase 6 — `quant_shadow.py`（影子观察）
**读哪些列**：直接读 snapshot + price_map（Close-only）：
- Snapshot：`Scan_Date, Ticker, Name, Sector, Quant_Score, Market_Regime, VIX, Price`
- Snapshot 因子：`RAW_FACTORS`（横截面 percentile 打分，`:105-109`）
- `Final_Score`、`Tag`：**条件读取**——`if "Final_Score"/"Tag" in day.columns`（`:190-191, :170-171`）。**当前 34 列 snapshot 不含这两列**，故实际走降级分支（Existing 选择回退为 `Quant_Score` 前 top_k）。
- 前瞻收益：`forward_return_nd`（Close-only，`:224`）。
- 是否用 OHLCV：**否**。

### Phase 7 — `quant_production.py`（生产治理）
**读哪些列**：只读治理产物，完全不碰 snapshot / price history：
- `quant_factor_validation.csv` → `Status` 列（research gate，`:196-203`）
- `quant_walk_forward_summary.csv` / `quant_walk_forward_results.csv` → `model_statuses` / `Model` / `OOS_N`（walk-forward gate，`:209-225`）
- `quant_shadow_report.json` / `quant_shadow_snapshot.csv` / `quant_shadow_performance.csv`（shadow gate，`:231-250`）
- `approval/config/state/audit` 文件
- 是否用 OHLCV：**否**（纯状态机/审计层）。

---

## 5. 逐 Phase 对照表

| Phase | 模块 | 主要数据源 | 需要的列 | 是否需 OHLCV | 判定 |
|-------|------|-----------|----------|--------------|------|
| 2 回测 | `quant_factor_backtest` | snapshot + price_history | 24 因子 + Price + Technical_Date + Snapshot_Date + Market_Regime + Close | 否 | **够** |
| 3 验证 | `quant_factor_validation` | P2 backtest.csv | 同 P2 因子 + Forward_Return_ND + Technical_Date + Market_Regime | 否 | **够** |
| 4 候选 | `quant_score_v2` | P3 validation/correlation.csv | 静态因子名（来自 34 列） | 否 | **够** |
| 5 WF | `quant_walk_forward` | P2 backtest.csv | RAW_FACTORS + Quant_Score + Forward_Return_ND + Technical_Date + Market_Regime | 否 | **够** |
| 6 Shadow | `quant_shadow` | snapshot + price_map | 24 因子 + Quant_Score + Price + Scan_Date + Market_Regime + VIX +（Final_Score/Tag 可选） | 否 | **部分够** |
| 7 治理 | `quant_production` | P3/P5/P6 产物 + 治理文件 | 下游产物列（Status/Model/OOS_N/Scan_Date 等） | 否 | **够** |

---

## 6. 缺什么（如果有）

**仅 Phase 6 存在结构性缺口，且已优雅降级，不阻断运行**：

1. **`Final_Score` 不在 34 列 snapshot**
   - Phase 6 用 `r.get("Final_Score", "") if "Final_Score" in day.columns`（`:190`）。
   - 当前 snapshot 无此列 → `Existing_Final_Score` 恒为空串。
   - 影响：Shadow 输出里 Existing 的 Final Score 缺失，仅展示层面的信息损失，**不影响打分/对比逻辑**。

2. **`Tag`（Core_Dragon / Observation）不在 34 列 snapshot**
   - Phase 6 用 `day["Tag"].isin({"Core_Dragon","Observation"})` 判定 “Existing Selected”（`:170-172`）。
   - 当前 snapshot 无 `Tag` 列 → 回退到 `Quant_Score` 前 top_k 作为 Existing 选择（`:173-176`）。
   - 影响：Shadow 的 “现有系统选中” 判定口径与真实 Core/Observation 选择**不完全一致**（用 Quant_Score 前 k 近似）。这是 Selection-Bias 对照的口径偏差，但在 SHADOW_ENABLE=false（默认禁用，`:63`）且当前尚处研究期，影响有限。

> 其余 6 个 Phase 所需列**全部已在 34 列 snapshot 或下游产物中齐备**，无缺失。

---

## 7. 是否需要补采 OHLCV（只列方向，不实施）

**当前结论：不需要补采。** 证据链：
- 前瞻收益口径在 `quant_factor_backtest.py:27-32` 被显式固定为 **Close[T] → Close[T+n]**；
- 价格历史 `quant_factor_price_history.csv` 只存 `Close`（`quant_factor_price.py:39`），且所有未来收益计算（`forward_return_nd`）只消费 Close；
- Phase 2/5/6 直接算/用前瞻收益，Phase 3/4/7 只消费上游产物——**没有任何一处引用 Open / High / Low / Volume**。
- Volume 相关因子（`Volume_Ratio_5D` / `Volume_Ratio_20D`）已在 Phase 1 计算时由原始 Volume 派生并**落为比率列**进 snapshot，下游无需原始 Volume。

**未来若扩展研究，以下方向会触发 OHLCV 补采（仅方向，不实施）**：

| 触发场景 | 需要补采的列 | 说明 |
|----------|--------------|------|
| 用 **Open** 计算前瞻收益以消除隔夜跳空（避免 T 日收盘→T+1 开盘的 look-ahead 争议） | `Open` | 改 `forward_return_nd` 的基准/目标口径 |
| 用 **High/Low** 做真实进场/出场模拟（止损/止盈回测、ATR 真实波动区间） | `High`, `Low` | 当前 ATR 已存为比率，但区间模拟需原始高低 |
| 用 **Volume** 做流动性/交易成本/放量见顶等信号建模 | `Volume` | 当前仅存比率，原始量为 0/均值假设 |

> 若决定补采，建议**只扩展 `quant_factor_price_history.csv` 的列**（加 `Open/High/Low/Volume`，保持 `Date|Ticker` 主键与 upsert 语义），**不必改动 34 列 snapshot**——因为 snapshot 是 T 日因子横截面，价格历史才是对未来收益的逐日追踪层。此项为可选增强，非 Phase 2–7 现状的阻塞项。

---

## 附：核对要点速查

- `SNAPSHOT_COLUMNS` 34 列：`quant_factor_lab.py:68-81`
- `PRICE_HISTORY_COLUMNS`（Close-only）：`quant_factor_price.py:39`
- Forward return 算法（仅 Close）：`quant_factor_backtest.py:89-116`
- Phase 6 条件读取 `Final_Score`/`Tag`：`quant_shadow.py:170-176, 190-191`
- Phase 6 降级回退：`quant_shadow.py:173-176`
- 全链路无 OHLCV 引用：已逐文件确认（P2/P3/P4/P5/P6/P7 均无 `Open`/`High`/`Low`/`Volume` 读取）
