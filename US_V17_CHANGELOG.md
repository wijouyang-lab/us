# US Scan V17

- GPT/ClawSocket 路由沿用 V16；不改已验证成功的 AI 接口。
- 核心 PCE：BEA 官方页面增加 www/bea.gov 双 URL + 多正则容错。
- HAWKISH_REPRICING：Technology/Communication 等观察行业提高 AI 候选准入技术确认门槛；Core 再提高 Quant 下限至 68，不做永久黑名单。
- 期权：Yahoo IV 缺失时，使用真实 bid/ask mid 或 last 反解 Black-Scholes IV，并据此计算 Call Delta；增加 IV_Source。
- 不伪造 Greeks；无法从真实报价反解时仍保留 N/A。
