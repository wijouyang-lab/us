# V14

针对 V13 的 `Request is missing a model`：

- 启动预检 `/v1/models`。
- 精确模型可用就原样使用；不可用时只从网关真实公布的模型中选择 fallback。
- 支持 `GPT_FALLBACK_MODEL` 与 `CLAWSOCKET_AUTO_FALLBACK`。
- Base URL 可填根地址、`/v1` 或完整 endpoint。
- Chat 使用 `max_tokens`。
- 错误中增加 `/v1/models` 模型摘要。

推荐：`GPT_MODEL=gpt-6-astra`；若 ClawSocket 当前账户尚未开放 Astra，保持 `CLAWSOCKET_AUTO_FALLBACK=1`，系统会自动使用网关实际提供的 GPT 模型，不再把“AI失败”静默伪装成正常 AI 评分。
