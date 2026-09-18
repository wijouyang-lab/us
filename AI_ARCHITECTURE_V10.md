# US Scan AI Architecture v10

## 模型分工

- GPT-6 Astra：Scan、Review、Evolve 主分析模型。
- Claude Opus 5：只做 Evolve 独立红队审查，不直接写交易账本，也不直接改变 Core/Observation。
- Python：最终裁判。硬门槛、Quant、Core/Observation、pending、止损、期权均由程序决定。

这样可以避免“同一个模型自己提出规则、自己证明规则”的闭环偏差。

## API 路由

`ai_router.py` 优先使用 OpenAI 原生 Responses API 调用 GPT-6 Astra。推荐配置：

- `GPT_API_KEY`
- `GPT_BASE_URL`（可留空，使用 OpenAI 默认地址）
- `GPT_MODEL=gpt-6-astra`

Claude 红队配置：

- `CLAUDE_API_KEY`
- `CLAUDE_BASE_URL`（可留空，使用 Anthropic 默认地址）
- `CLAUDE_AUDIT_MODEL=claude-opus-5`

为避免旧部署突然停止，若未配置 `GPT_API_KEY/OPENAI_API_KEY`，Astra 会回退到现有 `CLAWSOCKET_API_KEY/CLAWSOCKET_BASE_URL` 的兼容层。配置新 Secrets 后会自动使用原生 OpenAI 路由。

## Evolve 安全链

`GPT 提出规则 -> Claude 红队审计 -> 时间顺序 OOS 验证 -> Python 落地`

Claude 返回的 `approved_rule_ids` 决定哪些 prompt patch 可以进入 `evolved_rules.json`。Core 分数阈值只有在 OOS 合格且 Claude 红队允许时才自动修改。

## 新闻源分层

新增了三类独立证据：

1. Reuters 定向 Google News RSS：补充市场/公司事件新闻。
2. Federal Reserve 官方 RSS：政策与 FOMC/央行事实证据。
3. BLS 官方 RSS：CPI、就业等经济发布证据。

现有 CNBC、MarketWatch、Google News 和 Yahoo Finance RSS 继续作为补充。AI 提示中规定官方 Fed/BLS 与 Reuters 的优先级高于普通聚合新闻；来源冲突时不得直接扩大结论。

## 不改动的部分

- 不用 AI 决定真实期权合约价格。
- 不用 Claude 直接否决某只股票。
- 不自动扩大 Core 数量以凑 5 只。
- 不覆盖旧交易历史 CSV。
