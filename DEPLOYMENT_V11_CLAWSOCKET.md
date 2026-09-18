# V11 部署说明 — ClawSocket 统一中转

## 只需要配置两个 AI Secrets

GitHub → Settings → Secrets and variables → Actions：

```text
CLAWSOCKET_API_KEY
CLAWSOCKET_BASE_URL
```

推荐：

```text
CLAWSOCKET_BASE_URL=https://api.clawsocket.com
```

如果你原来填写的是：

```text
https://api.clawsocket.com/v1
```

也可以，路由层会自动处理。

## 模型

```text
GPT_MODEL=gpt-6-astra
CLAUDE_AUDIT_MODEL=claude-opus-5
```

工作流已经直接从 GitHub Secrets 读取 ClawSocket Key/Base URL；不再要求 GPT_API_KEY、GPT_BASE_URL、CLAUDE_API_KEY、CLAUDE_BASE_URL。

## 新架构

```text
ClawSocket
 ├─ OpenAI-compatible → GPT-6 Astra
 └─ Anthropic-compatible → Claude Opus 5
```

## 第一次运行前建议

先手动运行 Scan，确认日志出现：

```text
启动：宏观驱动美股扫描引擎 | 主模型: gpt-6-astra | AI路由: ai_router
```

然后观察 AI 请求是否成功。Evolve 再确认 Claude 红队审计是否出现。
