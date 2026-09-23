# V28 Short Put / Wall 修复

- Call Wall / Put Wall：仅当期权链存在有效 openInterest 时显示；否则 N/A，不再把最低执行价冒充 Wall。
- Short Put：仅对长期价值门槛通过的 Core 候选尝试。
- 默认窗口：45–90 DTE。
- 执行价：正股下方约 3%–15%。
- Delta：绝对值 0.15–0.35，目标约 0.25。
- 财报距到期/开仓 14 天内：Short Put 直接过滤。
- 记录有效接货价、现金担保、权利金收益率、年化简单折算、指派风险。
- Review 会对 Short Put 读取真实 Put 报价并按“收取权利金”的方向计算当前浮盈亏。
