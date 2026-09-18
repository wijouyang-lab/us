# ClawSocket V15.2

## 本版解决的问题

V15.1 已确认 Scan 端的 JSON `model` 与 `x-openclaw-model` 都能写入，但真实 POST 仍返回 `Request is missing a model, which is required.`。这意味着 `/v1/models` 目录可见性不能作为“真实路由可用”的充分条件。

### V15.2 修改

1. GPT 协议默认顺序调整为：
   - `/v1/chat/completions`
   - 失败再尝试 `/v1/responses`
2. 增加真实 POST 路由错误识别：
   - `missing a model`
   - `model is required`
   - `model not found`
   - `unknown/invalid model`
3. 当目标模型在 `/v1/models` 中存在，但真实 POST 仍报模型路由错误时：
   - 不再反复用同一模型重试；
   - 从 `/v1/models` 实际公布的模型中选择运行时备用模型；
   - 默认优先 `gpt-5.6-sol`，其次 `gpt-5.6-terra / gpt-5.6-luna / gpt-5.5 / gpt-5.4 / gpt-5 / gpt-4o-mini`；
   - 日志明确显示实际使用的备用模型。
4. GitHub Actions 显式开启运行时 fallback，并默认指定 `gpt-5.6-sol` 为第一备用。
5. 用户仍可通过：
   - `CLAWSOCKET_RUNTIME_FALLBACK=0` 关闭运行时 fallback；
   - `GPT_RUNTIME_FALLBACK_MODEL=<模型ID>` 指定第一备用模型。

## 为什么这样改

ClawSocket 的公开 OpenAI-compatible 接入资料以 `/v1/chat/completions` 为通用入口；模型可见性和实际 POST 路由应分开验证。
