# 死亡解剖：换手率 / IC 衰减 / 归因

> 脚本：`tools/research/turnover_and_cost_analysis.py`

## 1. 行业轮动收益与换手成本

⚠️ **本轮不计算行业轮动毛/净收益或换手成本。**
> 原因：缺少 research_sector_history_pit.csv；当前 Sector 映射不能替代历史 PIT 行业归属。
> 不允许把当前 `sp500_constituents.csv` 的现行行业标签套回两年历史，也不复用旧的硬编码 +0.1701% 毛超额。
> 之前报告的 −0.184% 是基于当前行业映射的探索性估计，尚未通过 PIT 行业归属验证；不能把它当作已验证的净 Alpha 结论。

## 2. IC 衰减（数据受限）

⚠️ **无法生成完整的 T+1~T+20 连续衰减曲线**：
`research_backtest_sp500_pit_2y.csv` 只提供 **5D / 10D / 20D** 三档前瞻收益，
**没有逐日前瞻列** ⇒ 只能给出三点，无法定位【第几天衰减到 0】。
IC 按每个 `Scan_Date` 单独计算横截面 Spearman 相关，再对日期取均值；不使用混合所有日期的 pooled correlation。

| 期限 | BP 日均 IC | BP 有效日期 | Momentum 日均 IC | Momentum 有效日期 | Momentum 正 IC 日期占比 |
|---|---:|---:|---:|---:|---:|
| 5D | N/A | 0 | -0.0096 | 458 | 52.8% |
| 10D | N/A | 0 | -0.0113 | 453 | 49.2% |
| 20D | N/A | 0 | +0.0012 | 443 | 50.1% |

> 日均 IC 是因子预测相关性，不是扣成本后的可交易策略收益；不同日期的 IC 仍可能存在序列相关。

## 3. BP 归因回归（必须有真实 PIT 市值与 PIT 行业）

⚠️ **本轮不输出 BP 的风格调整 t 值。**
> 原因：缺少 research_sector_history_pit.csv；当前 Sector 映射不能替代历史 PIT 行业归属。
> 缺少 Market_Cap 时严格跳过；禁止继续把 `log(Price)` 当作 Size 代理。

## 4. 数据完整性与限制

1. `research_sector_history_pit.csv` 必须含 `Ticker, Effective_From, Effective_To, Sector`；区间重叠、缺失或覆盖低于 99% 时不计算行业收益。
2. 当前 `research_fundamentals_pit_corrected.csv` 若没有真实 `Market_Cap`，BP 市值归因会跳过，不会用 `log(Price)` 静默替代。
3. 现有换手模型只估算等权行业篮子的权重更换，非个股级订单流或实际成交成本。
4. IC 衰减只有 5D / 10D / 20D 三个点；缺少每日前瞻收益时不推断更短衰减期。
