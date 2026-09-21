# US V18 — PCE + Option Quality

## 本版增强

1. 不改变已经验证成功的 GPT-6 Astra / ClawSocket `chat` 路由。
2. Core PCE 读取升级：
   - FRED
   - BEA 官方 Core PCE 专题页
   - 自动发现 BEA Personal Income and Outlays 官方新闻稿
   - 官方 release 兜底
   - 原有新闻文本 / Google News 继续保留
3. BEA 解析不再依赖“月份 | 数值”的固定 HTML 格式，而是解析页面文本与官方新闻稿句式。
4. CALL Debit Spread 增加执行质量门槛：
   - Reward/Risk >= 0.40
   - Break-even 相对正股 <= 12%
   - Net Debit <= 正股价格 4%
5. Long Call 兜底也必须满足 Break-even <= 12% 且权利金 <= 正股价格 4%，否则不推荐。
6. CSV 新增：RewardRisk / BreakevenPct / DebitPctOfSpot。
7. 日志直接显示最大亏损、最大收益、Break-even、R/R、Delta、IV。

## 设计原则

“有期权链”不等于“应该推荐”。
只有同时满足真实报价、风险预算和基本收益/风险结构，才进入 Scan→Option。

IV/Delta 仍只来自 Yahoo 链或真实市场 mid/last 的 Black-Scholes 反解，不使用虚构 IV。
