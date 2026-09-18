# ClawSocket V15.3

日期：2026-09-18

## AI 备用模型策略

主模型固定为：`gpt-6-astra`

当出现以下任一情况时，唯一允许的备用模型为：`claude-fable-5-1`

- gpt-6-astra 不在 `/v1/models`
- gpt-6-astra 在真实 POST 阶段返回 model 路由错误
- `/v1/chat/completions` 与 `/v1/responses` 均无法调用 Astra

不再自动切换到 `gpt-5.6-sol`、`gpt-5.6-luna`、`gpt-5.5` 等其他 GPT 模型。

可选环境变量：

`CLAUDE_RUNTIME_FALLBACK_MODEL`：默认 `claude-fable-5-1`。

实际成功使用备用模型时，日志会显示：

`✅ [ClawSocket] 运行时备用模型成功：claude-fable-5-1 (...)`
