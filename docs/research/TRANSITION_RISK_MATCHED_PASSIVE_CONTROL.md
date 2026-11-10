# QQQ Transition 风险匹配被动对照审计

日期：2026-11-03  
状态：**历史诊断完成；不构成策略验证或部署建议**

## 1. 研究问题

对 PR #438 的 QQQ Transition 5-day reversal 三档账户（25%、50%、100% sleeve），分别构造不使用任何预测信号的 QQQ/BIL 被动组合，使其全样本年化日波动率与对应 Transition NAV 完全匹配。比较在相同历史波动水平下，Transition 的 CAGR、Sharpe、最大回撤和成本是否优于简单被动资产配置。

## 2. 数据与来源

- 源 PR：[#438](https://github.com/wijouyang-lab/us/pull/438)
- 源 HEAD：`9b6effa6b76d860e583ba5b2edd9d79083997ffd`
- 日期：**2007-05-30 至 2026-10-30**
- 共同样本：**4,888 个 SPY session**
- Transition 版本：`w25_c10_all_legs`、`w50_c10_all_legs`、`w100_c10_all_legs`
- 原始来源 Git blob SHA 已固定于 `data/research/transition_risk_match/source_manifest.json`。

本对照提取 PR #438 三条每日 NAV 序列，并使用该 PR 的 QQQ/BIL 行情。执行和估值严格沿用 PR #438 的价格变换：`AdjOpen = raw Open * AdjClose / raw Close`，交易用 AdjOpen，日终标记用 AdjClose。

## 3. 预先写明的计算规则

1. 目标风险是各 Transition 版本全样本日收益标准差（样本标准差，ddof=1）乘以 `sqrt(252)`。
2. 被动组合不使用 Transition 信号或市场状态；目标 QQQ/BIL 权重在每个样本内固定。
3. 每月最后一个交易日确定目标，下一月首个 session 的 AdjOpen 恢复权重。
4. 采用 fractional shares，long-only，无杠杆。
5. 所有实际执行的再平衡订单腿均扣 10 bps；初始建仓不扣费，以匹配 PR #438 初始 BIL reserve 的处理方式。
6. 分红通过 AdjClose 调整价格隐含，不另建现金分红账本。
7. 用全样本数据反求被动 QQQ 权重，因此这是**事后风险匹配诊断**，不是可在样本开始前确定的策略参数，也不是独立样本外检验。

## 4. 结果

| Transition sleeve | Transition 波动 | 风险匹配 QQQ/BIL 权重 | Transition CAGR | 被动 CAGR | Transition MaxDD | 被动 MaxDD | Transition Sharpe | 被动 Sharpe | Transition 成本 | 被动成本 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 25% | 2.27% | 10.41% / 89.59% | 1.86% | 2.99% | -6.37% | -5.49% | 0.82 | 1.31 | $1901 | $122 |
| 50% | 4.33% | 19.93% / 80.07% | 2.28% | 4.42% | -12.01% | -11.35% | 0.54 | 1.02 | $3802 | $238 |
| 100% | 8.17% | 37.40% / 62.60% | 3.03% | 7.01% | -21.33% | -22.24% | 0.41 | 0.87 | $7605 | $449 |

风险匹配后的被动权重：

- 25% Transition 风险：QQQ **10.41%** / BIL **89.59%**
- 50% Transition 风险：QQQ **19.93%** / BIL **80.07%**
- 100% Transition 风险：QQQ **37.40%** / BIL **62.60%**

三档被动对照的全样本波动率与对应 Transition 版本误差均小于 1e-8。三档被动组合 CAGR 和 Sharpe 均高于对应 Transition 版本；在 25% 与 50% 风险档，被动组合的最大回撤也较小。100% 风险档被动组合的最大回撤略深，但 CAGR 与 Sharpe 明显更高。

## 5. 分阶段表现

分段为 2007-2015、2016-2020、2021-2026。三档风险匹配被动组合的 CAGR 在三个分段均高于对应 Transition 版本。具体逐段值保存在 `results.json`。

这并不意味着被动组合将来一定胜出；所有权重仍由完整历史样本事后反求，存在明显的样本内选择限制。

## 6. 成本与换手

每档被动组合均有 233 个月度再平衡 session、466 条订单腿。被动换手成本分别约为 **$121.84 / $237.67 / $448.65**。对应 Transition 版本按其原报告累计成本分别约 **$1901.21 / $3802.43 / $7604.85**。

被动组合尽管交易腿较多，但每月只是恢复较小权重漂移，累计交易名义金额及成本仍低于频繁切换风险 sleeve 的 Transition 账户。

## 7. 结论

**在 PR #438 的 2007-2026 历史样本中，Transition 5-day reversal 没有显示出相对同波动 QQQ/BIL 被动配置的增量优势。** 三档的被动 CAGR 和 Sharpe 均更高，成本也更低；25% 和 50% 档的回撤也更浅。100% 档被动回撤略深，但风险调整后收益仍优于 Transition。

本轮结果支持把 PR #438 的策略保留为探索性研究候选，不应把其历史表现解释为已验证 alpha。**不得据此部署、合并或发送订单**。权重是全样本事后匹配，价格采用调整价代理成交；这项分析不能代替真实原始开盘成交数据、独立前瞻观察或 PIT/幸存者偏差修复。

## 8. 自动化验证

- 固定 4,888 session 输入并在 manifest 中记录源 Git blob SHA；
- 核验日期唯一、严格递增、价格及 NAV 正值、有限；
- 断言三档匹配波动误差不超过 1e-8；
- 断言月度再平衡 session 数和订单腿数量；
- 断言成本等于实际交易名义金额乘 10 bps；
- 断言三档被动 CAGR 高于对应 Transition 的历史诊断结果。
