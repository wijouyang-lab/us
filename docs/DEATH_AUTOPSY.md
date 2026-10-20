# 死亡解剖：换手率 / IC 衰减 / 归因

> 脚本：`tools/research/turnover_and_cost_analysis.py`
> **状态：行业收益和风格归因已设为 fail-closed；当前缺少完整 PIT 输入，因此本版不输出新的净 Alpha 数值。**

## 1. 行业轮动收益与换手成本

⚠️ **本轮不计算行业轮动毛/净收益或换手成本。**

> 原因：缺少 `research_sector_history_pit.csv`。当前 `sp500_constituents.csv` 里的行业标签不能替代两年历史 PIT 行业归属。
>
> 旧版报告曾给出毛超额 **+0.1701%**、成本 **0.354%**、净超额 **−0.184%**。这些数字基于当前行业映射回填历史，只能作为探索性记录；在 PIT 行业归属重建前，**不能视为已验证的策略收益或净 Alpha**。

重新启用行业回测前，`research_sector_history_pit.csv` 必须提供 `Ticker, Effective_From, Effective_To, Sector`。区间重叠、缺失或匹配覆盖率低于 99% 时，脚本将继续跳过行业结果。行业换手模型仍是等权行业篮子的近似，不能替代逐只股票的实际换手、市场冲击和容量分析。

## 2. IC 衰减（数据受限）

⚠️ **无法生成完整的 T+1~T+20 连续衰减曲线。**

`research_backtest_sp500_pit_2y.csv` 只提供 **5D / 10D / 20D** 三档前瞻收益，没有逐日前瞻列，因此不能确定信号在第几天衰减到零。下面的相关性是因子统计，不是扣除成本后的可交易策略收益。

| 期限 | BP 的 IC | Momentum 的 IC |
|---|---|---|
| 5D | N/A（需单独计算） | −0.0270（n=220380） |
| 10D | N/A（需单独计算） | −0.0362（n=217873） |
| 20D | N/A（需单独计算） | −0.0343（n=212869） |

## 3. BP 归因回归（真实市值 + PIT 行业必需）

⚠️ **本轮不输出 BP 的风格调整 t 值。**

> 当前 `research_fundamentals_pit_corrected.csv` 的字段只有 `Date, Ticker, EP_TTM, BP, ROE_ANN, Price`，没有真实的 `Market_Cap`；当前仓库也缺少 PIT 行业历史。因此旧版的 `log(Price)` 代理回归及 t=1.23 不再作为有效归因结论。

归因脚本现在要求同时具备按日期匹配的真实 `Market_Cap` 与 PIT Sector；任何一项缺失都跳过回归，不再把股价静默当作市值代理。

## 4. 数据完整性与限制

1. PIT 行业历史需包含 `Ticker, Effective_From, Effective_To, Sector`；区间重叠或覆盖率低于 99% 时，行业回测不运行。
2. 缺少 `Market_Cap` 时，BP 市值归因不运行；不再使用 `log(Price)` 代替公司规模。
3. 行业换手率仍只是等权行业篮子的代理，不能解释为真实个股订单换手。
4. IC 衰减只有 5D / 10D / 20D 三个点；缺少每日前瞻数据时不外推更短期限。
5. 缺乏 PIT 输入不是“零收益”或“策略失败”的证据，而是该项实证结论目前不可验证。
