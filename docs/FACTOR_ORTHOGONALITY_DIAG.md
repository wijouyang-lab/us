# 因子正交性诊断报告（S&P500 PIT 2Y）

> 自动生成于 `tools/research/factor_orthogonality_diag.py`
> 样本：`research_factor_snapshots_sp500_pit_2y.csv` ∩ `research_backtest_sp500_pit_2y.csv`（target=`Forward_Return_5D`）
> 可用行数：**200,000**（含 17 个因子）

## 1. 高相关因子对（|Spearman ρ| > 0.7）

| 因子 A | 因子 B | ρ |
|---|---|---|
| `MA20` | `MA50` | **+0.998** |
| `ZScore_20D` | `乖离率(%)` | **+0.950** |
| `RSI` | `乖离率(%)` | **+0.927** |
| `Momentum_20D_Pct` | `MA20_Slope_Pct_5D` | **+0.922** |
| `ZScore_20D` | `RSI` | **+0.921** |
| `Realized_Volatility_20D_Pct` | `ATR_Pct` | **+0.884** |
| `Momentum_20D_Pct` | `Stock_RS_20D_vs_SPY` | **+0.880** |
| `Momentum_20D_Pct` | `RSI` | **+0.869** |
| `Momentum_5D_Pct` | `KDJ_J` | **+0.843** |
| `Momentum_20D_Pct` | `乖离率(%)` | **+0.834** |
| `Stock_RS_20D_vs_SPY` | `MA20_Slope_Pct_5D` | **+0.810** |
| `Momentum_20D_Pct` | `ZScore_20D` | **+0.789** |
| `RSI` | `MA20_Slope_Pct_5D` | **+0.785** |
| `ZScore_20D` | `KDJ_J` | **+0.784** |
| `Stock_RS_20D_vs_SPY` | `RSI` | **+0.783** |
| `Volume_Ratio_20D` | `量比` | **+0.758** |
| `Momentum_5D_Pct` | `ZScore_20D` | **+0.751** |
| `Stock_RS_20D_vs_SPY` | `乖离率(%)` | **+0.751** |
| `乖离率(%)` | `MACD_HIST_LAST` | **+0.740** |
| `乖离率(%)` | `KDJ_J` | **+0.735** |
| `Momentum_5D_Pct` | `乖离率(%)` | **+0.716** |
| `ZScore_20D` | `MACD_HIST_LAST` | **+0.714** |
| `ZScore_20D` | `Stock_RS_20D_vs_SPY` | **+0.703** |

## 2. VIF（方差膨胀因子 > 10 视为严重共线）

| 因子 | VIF | 判定 |
|---|---|---|
| `MA20` | 589.27 | ⚠️ >10 |
| `MA50` | 588.54 | ⚠️ >10 |
| `Momentum_20D_Pct` | 20.97 | ⚠️ >10 |
| `MA20_Slope_Pct_5D` | 11.84 | ⚠️ >10 |
| `乖离率(%)` | 11.20 | ⚠️ >10 |
| `RSI` | 10.75 | ⚠️ >10 |
| `ZScore_20D` | 7.10 | ok |
| `Stock_RS_20D_vs_SPY` | 6.56 | ok |
| `ATR_Pct` | 4.48 | ok |
| `Volume_Ratio_20D` | 4.34 | ok |
| `量比` | 4.31 | ok |
| `Realized_Volatility_20D_Pct` | 4.06 | ok |
| `Momentum_5D_Pct` | 3.79 | ok |
| `KDJ_J` | 3.49 | ok |
| `Momentum_60D_Pct` | 2.03 | ok |
| `MACD_HIST_LAST` | 1.45 | ok |
| `Beta_60D_SPY` | 1.41 | ok |

**VIF > 10 的因子数：6**

## 3. 单因子 vs 多因子（岭回归）

| 模型 | R² | 说明 |
|---|---|---|
| A) `ATR_Pct` 单因子 OLS | **0.006740** | 基准 |
| B) 全因子 Ridge（α=0.01） | **0.008151** | 17 因子 |

**R² 增量 = +0.001410**（相对提升 20.9%）

### Top 5 重要特征（Ridge α=0.01，标准化系数）

| 因子 | β（标准化） |
|---|---|
| `ATR_Pct` | +0.004388 |
| `Stock_RS_20D_vs_SPY` | +0.001821 |
| `Momentum_5D_Pct` | -0.001601 |
| `量比` | +0.001174 |
| `KDJ_J` | +0.000754 |

### ATR_Pct 与其最相关的 5 个因子

| 因子 | Spearman ρ |
|---|---|
| `Realized_Volatility_20D_Pct` | +0.884 |
| `Beta_60D_SPY` | +0.445 |
| `RSI` | -0.159 |
| `Momentum_60D_Pct` | -0.146 |
| `Momentum_20D_Pct` | -0.124 |

## 4. 结论

- ⚠️ 存在 **23** 对高相关因子、**6** 个 VIF>10 因子 → **存在冗余**。
- ○ 提升仅 **0.0014** → **边际，需谨慎**。
- 注意：R² 极低（~0.0082）属日频因子常态；R² 提升 ≠ 可交易 alpha。
