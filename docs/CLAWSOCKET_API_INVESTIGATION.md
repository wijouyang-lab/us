# ClawSocket 接口只读调查（新闻翻译功能前置）

> 只读调查，未改任何代码、未 push/rebase/fetch、未碰监控 PID 108842、未跑真实 scan。
> 行号以当前 `/tmp/us` 为准。

---

## 1. ClawSocketClient 完整接口摘要

**文件**：`/tmp/us/clawsocket_compat.py`（约 355 行，纯 Python，仅依赖 `requests`）

| 项 | 位置 | 说明 |
|---|---|---|
| 类定义 | `:35 class ClawSocketClient` | OpenAI/Anthropic 双协议兼容客户端 |
| 构造 | `:36 __init__(api_key=None, base_url=None, timeout=300, retries=2)` | timeout 300s，retries 2 次 |
| key 读取 | `:37` | `api_key or os.environ.get("CLAWSOCKET_API_KEY")` |
| base_url 读取 | `:38` | `base_url or os.environ.get("CLAWSOCKET_BASE_URL") or "https://api.clawsocket.com"` |
| 模型发现 | `:62 _load_models` | GET `/v1/models`（30s 超时） |
| 模型解析 | `:94 _resolve_model` | 目录无匹配时自动 fallback（`CLAWSOCKET_AUTO_FALLBACK` 默认开） |
| 真实探测 | `:111 live_probe` | 一次真实 POST 验证路由，成功后写 `CLAWSOCKET_LIVE_MODEL/PROTOCOL` |
| 请求分发 | `:277 _request` | 优先复用 live 路由，否则按 variants × protocol 遍历 |
| HTTP 重试 | `:219 _post` | 见 §3 |

**消息入口**（`scan.py` 实际用的是这两个）：
- `client.messages.create(**kwargs)`（`:31-33`）→ 同步返回 `_Response`（`.output_text` / `.content` / `.raw`）
- `client.messages.stream(**kwargs)`（`:30`）→ `_StreamContext`（**注意：非真 SSE**，见 §3）

---

## 2. 模型名 + endpoint + key 环境变量

| 项 | 实际值 / 来源 | 位置 |
|---|---|---|
| **模型名** | `TARGET_MODEL = os.environ.get("GPT_MODEL") or "gpt-6-astra"` | `scan.py:62` |
| 默认模型 | **`gpt-6-astra`** | 同上 |
| fallback 候选 | `["gpt-6-astra", "gpt-5.4", "gpt-5.3-codex", "gpt-5.2"]` | `clawsocket_compat.py:91` |
| **key 环境变量** | `CLAWSOCKET_API_KEY`（必需，缺失报错） | `clawsocket_compat.py:37`、`scan.py:144` |
| **base_url 环境变量** | `CLAWSOCKET_BASE_URL`（默认 `https://api.clawsocket.com`） | `clawsocket_compat.py:38` |
| endpoint 协议 | gpt → `["chat", "responses"]`；claude → `["anthropic", "chat"]` | `clawsocket_compat.py:252-256` |
| 具体路径 | chat=`/v1/chat/completions`(:244)、responses=`/v1/responses`(:239)、anthropic=`/v1/messages`(:250)、models=`/v1/models`(:67) | — |

**其它可选环境变量**（均非必需）：`GPT_FALLBACK_MODEL` / `CLAUDE_FALLBACK_MODEL` / `CLAWSOCKET_AUTO_FALLBACK` / `CLAWSOCKET_PROTOCOL`（auto/chat/responses/anthropic）/ `GPT_REASONING_EFFORT` / `CLAWSOCKET_ANTHROPIC_VERSION`；`CLAWSOCKET_LIVE_MODEL` / `CLAWSOCKET_LIVE_PROTOCOL` 为运行时写入，非手动配置。

**CI 注入方式**：`scan.yml`/`review.yml`/`evolve.yml` 均从 GitHub Secrets 注入 `CLAWSOCKET_API_KEY` + `CLAWSOCKET_BASE_URL`（`:47-50` 等）；`GPT_MODEL` 未显式设，走默认 `gpt-6-astra`。

---

## 3. 调用方式（batch / retry / JSON mode）

**调用模式：单条 prompt，非批量**。scan.py 有 5 个 AI 调用点，全部是"1 个 user message + 1 次请求"：

| 调用点 | 位置 | max_tokens |
|---|---|---|
| 市场信号 `analyze_market_signals` | `scan.py:2255` | 12000 |
| 持仓风控 `pre_scan_portfolio_review` | `scan.py:2518` | 3000 |
| 主报告 `generate_ai_report` | `scan.py:2756` | report_max_tokens |
| 最终解释 `enrich_verified_items_with_ai_details` | `scan.py:3137` | 10000 |
| 启动预检/实测 `preflight`+`live_probe` | `scan.py:213-222` | 16 |

- **无 batch/多消息批量接口**，每次调用只处理一段 prompt。
- **`_model_stream_text`（`scan.py:2030-2036`）名义叫 stream，实为同步**：`_StreamContext` 的 `text_stream` 只有 1 个完整文本元素，`join` 后返回全文——本质是"完整 POST + 全文返回"，非 SSE 逐 token。
- **retry/backoff**：`clawsocket_compat.py:219-232` `_post`，`retries=2`，对 `429/500/502/503/504` 与部分网络错误做 `time.sleep(2**(attempt-1))`（1s→2s）指数退避。
- **无 token 用量日志**：全仓 grep `usage` / `prompt_tokens` 无命中，调用不记录 token 消耗。
- **JSON mode**：**无 API 级 `response_format=json_object`**。现成成熟做法是"prompt 里要求只输出 JSON + `_extract_json_object`（`scan.py:2188`）手动提取"，容忍 ```json fence / 前后解释 / 字符串内花括号。

---

## 4. 能否复用做新闻翻译 —— **能（可直接复用）**

结论：**是**。理由：
1. `ClawSocketClient` 是独立纯 Python 类，`from clawsocket_compat import ClawSocketClient` 即可，不依赖 scan.py 的模块级副作用（无 sys.exit/时间门控）。
2. 复用同一套 key/base_url（已存在于 CI Secrets），同一默认模型 `gpt-6-astra`。
3. 翻译+sentiment 是纯文本任务，用 `client.messages.create(model="gpt-6-astra", messages=[...], max_tokens=...)` 单条调用即可；JSON 输出复用 `_extract_json_object` 解析。

**两个实施提示（判决后）**：
- `fetch_news.py` 目前纯 stdlib（urllib），import `clawsocket_compat` 会引入 `requests`——但 CI 已装 `requests`（scan 也在用），**不算新依赖**；或把翻译做成独立脚本与 fetch 分离。
- 用 `.messages.create()`（返回 `.output_text`）比 `.messages.stream()` 更直接（后者 text_stream 仅 1 元素，无真流式收益）。

---

## 5. 是否需要新环境变量 / 新依赖

| 项 | 结论 |
|---|---|
| 新环境变量 | **不需要**。复用 `CLAWSOCKET_API_KEY` + `CLAWSOCKET_BASE_URL`（CI 已配）；`GPT_MODEL` 可选覆盖 |
| 新依赖 | **不需要**。`clawsocket_compat.py` 仅依赖 `requests`（已装）；`_extract_json_object` 纯 stdlib |

---

## 6. 速率冲突风险与建议（cron 错开方案）

**风险面**：
- ClawSocket 的 rate limit **未在代码中明示**（无显式限流文档，仅 `retries=2` 指数退避兜底）。
- scan cron = `7 13 * * 1-5`（13:07 UTC 触发，AI 调用发生在 scan 技术面跑完后，约 13:15–13:45 区间）。
- news-fetch cron（拟）= `23 */2 * * 1-5`（每 2 小时 23 分）。

**结论与建议**：
1. **翻译务必批量**：30 条（或 ≤7 条）新闻在**一次 API 调用**内完成（prompt 给全部 headline，要求输出 JSON 数组），而非逐条调用。理由：需求本身要求"翻译与 sentiment 共用一次调用"；一次调用既省 token 又几乎无速率压力。
2. **天然隔离**：news 翻译的 AI 调用放在 `news-fetch` workflow 内，与 scan 的 AI 调用分属不同 workflow/触发时间，冲突概率低；批量 1 次调用即使撞上也仅 1 次，`retries=2` 可自愈。
3. **缓存降频**：`headline hash → {headline_cn, sentiment}` 的 JSON 缓存命中即跳过 API，新闻标题跨多次 fetch 通常不变，可大幅降低调用频次。
4. **错开确认**：13:07（scan）与每 2 小时的 23 分（news）当前已天然错开；若担心 14:23 与 scan 尾部 AI 调用重叠，可将 news cron 定为 `45 */2 * * 1-5`（与 23 分错开，且远离整点），判决后实施时定。
