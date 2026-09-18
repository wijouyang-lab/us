# US Stock Scanner V13

## 本版已处理

1. ClawSocket AI 接入改成双协议兼容层：
   - GPT 模型优先走 OpenAI Responses API：`/v1/responses`
   - Claude 模型优先走 Anthropic Messages API：`/v1/messages`
   - 若首选协议失败，再自动回退到 `/v1/chat/completions`
   - `CLAWSOCKET_PROTOCOL=auto` 为默认行为

2. GPT-6 Astra 不再发送 `temperature`；Responses 请求使用 `max_output_tokens`。

3. AI 调用失败时，不再把失败当成中性 AI=60 直接进入 Core。
   - AI 不可用：Core 自动禁止
   - 仍可生成程序化 Observation 兜底
   - 邮件明确显示 AI 不可用及原始错误

4. Event Regime 的 `hard_avoid_sectors` 正式接入程序硬门槛。
   - 当前事件+当前行业价格确认后的硬回避会在 AI 之前直接过滤
   - 历史规则仍不会变成永久黑名单

5. 核心 PCE 增加 BEA 官方页面备用源：
   `FRED -> BEA 官方 -> 已抓取新闻 -> Google News`

6. GitHub Actions 更新：
   - checkout v4
   - setup-python v5
   - 删除 Anthropic SDK 依赖
   - 支持 `GPT_MODEL`、`GPT_REASONING_EFFORT`、`CLAUDE_AUDIT_MODEL`、`CLAWSOCKET_PROTOCOL`
   - 扫描时提交 `scan_version.txt`
   - Evolve 不再使用 `|| true` 吞掉失败

## 推荐 Secrets

- `CLAWSOCKET_API_KEY`：你的 ClawSocket Key
- `CLAWSOCKET_BASE_URL`：`https://api.clawsocket.com` 或 `https://api.clawsocket.com/v1` 均可
- `GPT_MODEL`：可不设置，默认 `gpt-6-astra`
- `GPT_REASONING_EFFORT`：可不设置；设置时可用 `medium/high/xhigh/max`
- `CLAUDE_AUDIT_MODEL`：可不设置；默认 `claude-opus-5`
- `CLAWSOCKET_PROTOCOL`：建议不设置，让程序自动选择

## 本地验证

已通过：
- Python 编译检查
- GPT Responses mock 请求检查
- Claude Messages mock 请求检查
- 三个 GitHub Actions YAML 解析检查
- `claude_red_team_audit` 重复定义清理
