# AI Architecture V11 — ClawSocket Unified Routing

GPT-6 Astra 和 Claude 审计模型统一使用 ClawSocket 中转站余额。

## GitHub Secrets

只需要：

- `CLAWSOCKET_API_KEY`
- `CLAWSOCKET_BASE_URL`

`CLAWSOCKET_BASE_URL` 可以填写 `https://api.clawsocket.com` 或 `https://api.clawsocket.com/v1`，程序会自动规范化。

模型：
- `GPT_MODEL=gpt-6-astra`
- `CLAUDE_AUDIT_MODEL=claude-opus-5`

## 传输协议

- GPT：ClawSocket OpenAI-compatible `/v1/chat/completions`
- Claude：ClawSocket Anthropic-compatible `/v1/messages`

这意味着同一个 ClawSocket Key 可以同时承担 GPT 主分析和 Claude 红队审计，不要求另外配置官方 OpenAI / Anthropic Key。

## 模型职责

GPT-6 Astra：Scan、Review、Evolve 提议。

Claude：仅在 Evolve 做独立红队审计，不直接修改 strategy_params.json，也不直接写交易账本。

## 安全原则

1. 程序硬门槛高于 AI 文本。
2. Evolve 参数只有通过时序 OOS 验证且满足安全条件才允许落地。
3. Claude 只审查 GPT 的策略变化，不拥有直接写参数权限。
4. ClawSocket 请求失败不会自动把决策交给另一个未经验证的模型。
