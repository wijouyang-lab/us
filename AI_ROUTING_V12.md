# US AI Routing v12

## 统一入口
所有模型均通过 ClawSocket：

- `CLAWSOCKET_BASE_URL`：建议 `https://api.clawsocket.com`
- `CLAWSOCKET_API_KEY`
- GPT 主模型：`GPT_MODEL`，默认 `gpt-6-astra`
- Claude 红队：`CLAUDE_AUDIT_MODEL`，默认 `claude-opus-5`

代码统一走 OpenAI-compatible `/v1/chat/completions`，避免 Anthropic SDK 与中转站参数不兼容。

## 为什么修复 `temperature`
此前日志出现：`Messages.create() got an unexpected keyword argument 'temperature'`。
这是 SDK/中转兼容层参数不一致，不是市场数据问题。v12 路由层主动剥离 `temperature`，并对 429/5xx/超时自动重试。

## AI 失败安全策略
Scan 主报告失败时，不再只发“AI报告生成失败”。邮件会展示程序化 Quant/RSI/乖离率/技术确认兜底，并明确错误类型。

## Evolve
GPT-6 Astra 提出策略变化；Claude Opus 5 独立红队审计；只有 OOS 合格 + Claude 批准时，程序才允许自动修改 Core 门槛。
