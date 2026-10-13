# 模型切换调查：gpt-6-astra → opus 5.5（ClawSocket 中转站）

> 调查日期：2026-10-09 · **只读，未改任何代码，未 push/rebase**
> 一句话结论：**能改，但有三处硬编码 + 一个潜伏的崩溃 bug 必须先处理**；且「opus 5.5」的**准确模型 ID 无法在本地确认**（无 ClawSocket key），必须在 CI 用 `/v1/models` 核实。

---

## 1. gpt-6-astra 全仓引用点清单（文件 + 行号）

### 1.1 代码（.py）

| 文件 | 行号 | 内容 | 类型 |
|---|---|---|---|
| `ai_router.py` | 20 | `GPT_MODEL = os.getenv("GPT_MODEL", "gpt-6-astra")` | 默认值（可用 `GPT_MODEL` 覆盖） |
| `ai_router.py` | 186 | `model = model or GPT_MODEL` | 使用点 |
| `clawsocket_compat.py` | 91 | `defaults = [...] if startswith("claude") else ["gpt-6-astra","gpt-5.4","gpt-5.3-codex","gpt-5.2"]` | **硬编码** fallback 列表 |
| `clawsocket_compat.py` | 282 | 报错文案「请设置 GPT_MODEL / CLAUDE_AUDIT_MODEL」 | 文案 |
| `clawsocket_probe.py` | 4 | `requested=os.environ.get("GPT_MODEL") or "gpt-6-astra"` | 默认值（可覆盖） |
| `dashboard/fetch_news.py` | 61 | `TRANSLATE_MODEL = os.environ.get("GPT_MODEL") or "gpt-6-astra"` | 默认值（可覆盖） |
| `dashboard/fetch_news.py` | 281 | docstring「惰性复用 ClawSocketClient（gpt-6-astra）」 | 文案 |
| `evolve.py` | 17 | `EVOLVE_MODEL = os.environ.get("GPT_MODEL") or "gpt-6-astra"` | 默认值（可覆盖） |
| `review.py` | **50** | `TARGET_MODEL = "gpt-6-astra"` | ❗**硬编码，无 env 覆盖** |
| `review.py` | 3603 | `model=TARGET_MODEL` | 使用点 |
| `scan.py` | 62 | `TARGET_MODEL = os.environ.get("GPT_MODEL") or "gpt-6-astra"` | 默认值（可覆盖） |
| `scan.py` | 209,214-222 | 启动日志 + `preflight()` / `live_probe()` | 使用点 |
| `scan.py` | 2255 / 2518 / 2756 / 3137 | `model=TARGET_MODEL`（max_tokens 12000/3000/动态/10000） | 使用点 |
| `scan.py` | 2792 | 注释「gpt-6-astra 输出格式漂移…」 | 文案 |
| `tests/test_fetch_news.py` | **193** | `assert c.messages.recorded["model"] == "gpt-6-astra"` | ❗**测试断言，改了就红** |

### 1.2 已有的 Claude / opus 引用（重要！）

| 文件 | 行号 | 内容 |
|---|---|---|
| `ai_router.py` | 21 | `CLAUDE_AUDIT_MODEL = os.getenv("CLAUDE_AUDIT_MODEL", "claude-opus-5")` |
| `evolve.py` | 18 | `CLAUDE_AUDIT_MODEL = os.environ.get("CLAUDE_AUDIT_MODEL") or "claude-opus-5"` |
| `evolve.py` | 318 | `client.messages.create(model=CLAUDE_AUDIT_MODEL, ...)` ← **红队审计已经跑在 opus 上** |
| `clawsocket_compat.py` | 91 | claude fallback 默认 `["claude-opus-4-6","claude-sonnet-4-5-20250929"]` |
| `clawsocket_compat.py` | 252-256 | 协议计划：claude/anthropic 前缀 → `["anthropic","chat"]` |

**关键**：`claude-opus-5` **已经在生产里跑着**（evolve 红队审计，evolve.yml 每月 2:00 UTC 触发）。所以「切到 opus」不是从零开始，而是把 GPT 主模型的调用也迁到 Claude 侧。

### 1.3 文档（.md，非代码，可选同步）

`AI_ARCHITECTURE_V10.md:17`、`AI_ARCHITECTURE_V11_CLAWSOCKET.md:15`、`AI_ROUTING_V12.md:8`、`CLAWSOCKET_V13_CHANGELOG.md:37`、`CLAWSOCKET_V14_CHANGELOG.md:12`、`CLAWSOCKET_V15.2_CHANGELOG.md:20-22`、`CLAWSOCKET_V15.3_CHANGELOG.md:7-15`、`CLAWSOCKET_V16_CHANGELOG.md:6-11`、`DEPLOYMENT_V11_CLAWSOCKET.md:29`

---

## 2. ClawSocket 是否支持 opus 5.5？准确模型名？

### 2.1 发现机制（代码里确实有）

`clawsocket_compat.py` 有完整的模型发现：
- `available_models` / `_load_models()` → `GET {root}/v1/models`（`_headers_openai()`，timeout `min(timeout,30)`）
- `_resolve_model(requested)` → 精确匹配 → 大小写不敏感匹配 → `CLAWSOCKET_AUTO_FALLBACK` 开启时走 `_fallback_candidates()`
- `_fallback_candidates()` → 先读 `CLAUDE_FALLBACK_MODEL`（claude 前缀）或 `GPT_FALLBACK_MODEL`，再拼默认列表
- `_model_variants()` → `claude-*` 会额外试 `anthropic/claude-*`
- `_protocol_plan()` → claude 前缀优先 Anthropic `/v1/messages`
- `preflight()` / `live_probe()` → 启动期真实 POST 探测，成功后写 `CLAWSOCKET_LIVE_MODEL` / `CLAWSOCKET_LIVE_PROTOCOL`

### 2.2 但**本地无法确认** ❗

- 本沙箱**没有 `CLAWSOCKET_API_KEY` / `CLAWSOCKET_BASE_URL`**（`.env` 里只有 `FINNHUB_API_KEY=`，环境变量也没有）。
- 因此**无法调用 `/v1/models` 拉取真实模型清单**——这一步必须在 **GitHub Actions（有 Secret）** 里做。

### 2.3 从仓库里能推断出的命名规律

文档/代码里出现过的真实模型 ID：

| ID | 含义 |
|---|---|
| `gpt-6-astra` | 当前 GPT 主模型 |
| `claude-opus-5` | **opus 5**（已在用） |
| `claude-opus-4-6` | opus 4.6 |
| `claude-sonnet-4-5-20250929` | sonnet 4.5（带日期） |
| `claude-fable-5-1` | fable 5.1（V15.3 指定的唯一运行时备用） |
| `gpt-5.6-sol` / `gpt-5.6-luna` / `gpt-5.6-terra` / `gpt-5.5` / `gpt-5.4` | 历史 GPT 备用 |

**命名规律**：`claude-<family>-<major>-<minor>`（如 `opus-4-6` = 4.6、`fable-5-1` = 5.1）。
→ **「opus 5.5」最可能的 ID 是 `claude-opus-5-5`**，其次是 `claude-opus-5.5`。

⚠️ **但这是推测，必须先用 `/v1/models` 核实**。另需向用户确认一件事：仓库里现成的是 `claude-opus-5`，你说的「opus 5.5」是指 **5.5（`claude-opus-5-5`）**，还是其实就是要切到已存在的 **opus 5（`claude-opus-5`）**？

**核实方法**（在 CI 里跑一次即可）：
```bash
curl -s "$CLAWSOCKET_BASE_URL/v1/models" -H "Authorization: Bearer $CLAWSOCKET_API_KEY" \
  | python3 -c "import json,sys;print('\n'.join(m['id'] for m in json.load(sys.stdin)['data']))" | grep -i opus
```
或直接用仓库现成脚本 `clawsocket_probe.py`。

---

## 3. 改动清单（哪些文件改哪一行）

> 假设目标 ID = `claude-opus-5-5`（**待 /v1/models 确认后再落地**）

| # | 文件 | 行 | 改法 | 是否必须 |
|---|---|---|---|---|
| 1 | `review.py` | 50 | `TARGET_MODEL = "gpt-6-astra"` → `TARGET_MODEL = os.environ.get("GPT_MODEL") or "claude-opus-5-5"` | ✅ **必须**（唯一硬编码） |
| 2 | `scan.py` | 62 | 默认值 `gpt-6-astra` → `claude-opus-5-5` | ✅ 必须 |
| 3 | `evolve.py` | 17 | `EVOLVE_MODEL` 默认值 → `claude-opus-5-5` | ✅ 必须 |
| 4 | `dashboard/fetch_news.py` | 61 | `TRANSLATE_MODEL` 默认值 → `claude-opus-5-5` | ✅ 必须（新闻翻译） |
| 5 | `ai_router.py` | 20 | `GPT_MODEL` 默认值 → `claude-opus-5-5` | ⚠️ 该文件**无任何 .py 引用它**（`grep -rn "ai_router" --include="*.py"` 零命中），改不改都不影响运行时，但为一致性建议改 |
| 6 | `clawsocket_probe.py` | 4 | 默认值 → 目标 ID | 建议（诊断脚本一致性） |
| 7 | `clawsocket_compat.py` | 91 | GPT fallback 默认列表里的 `gpt-6-astra` 建议保留（作为 GPT 侧备用），**不要全删** | 建议保留 |
| 8 | `tests/test_fetch_news.py` | 193 | `assert ... == "gpt-6-astra"` → 改为目标 ID | ✅ **必须**（否则 221 测试变红） |
| 9 | 各 `.md` 文档 | 多处 | 文案同步 | 可选 |

**不需要改**：`review.py:3603`、`scan.py:2255/2518/2756/3137`、`evolve.py:416` —— 它们都引用 `TARGET_MODEL` / `EVOLVE_MODEL` 常量，改常量即全局生效。

---

## 4. 风险（模型切换会影响什么）

### 4.1 ❗**最高风险：潜伏的 AttributeError 崩溃**（本次切换会精准踩中）

`clawsocket_compat.py:324/326` 调用了两个**根本不存在**的方法：

```python
route_error_seen = any(self._looks_like_model_route_error(RuntimeError(err)) for err in all_errors)
if route_error_seen:
    for fallback in self._runtime_fallback_candidates(resolved):
```

运行时实测（`hasattr` 验证）：

```
_looks_like_model_route_error:  ❌ 未定义
_runtime_fallback_candidates:   ❌ 未定义
_fallback_candidates:           已定义
_model_variants:                已定义
_protocol_plan:                 已定义
_resolve_model:                 已定义
```

- 这两个方法在**全仓任何 .py 里都没有定义**（`grep -rn` 只有两处调用点）。
- 触发条件：`all_errors` 非空（即所有 model×protocol 尝试都失败）。
- `any()` 对**空**序列短路不调用 → 所以只要 gpt-6-astra 一直可用，这个 bug 就**永远不会暴露**（潜伏至今）。
- **切模型时极易触发**：一旦 `claude-opus-5-5` 不在 `/v1/models` 或 POST 路由失败 → 所有尝试失败 → `all_errors` 非空 → **抛 `AttributeError`，而不是设计中的「优雅降级到 claude-fable-5-1」**。

→ **必须先补上这两个方法（或把 324-343 整段包 try/except），再做切换。**

### 4.2 协议切换：OpenAI chat → Anthropic messages

`_protocol_plan()`：claude 前缀 → 先试 `anthropic`（`/v1/messages`），再 `chat`。
- Anthropic 路径会走 `_messages_to_anthropic()`：**system 消息被单独抽出**成顶层 `system` 字段。
- 现有 scan/review 的 prompt 都是单条 `user` message，无 system，影响可控。
- 但 `max_tokens` 语义：Anthropic 用 `max_tokens`，GPT responses 用 `max_output_tokens`（`_request_responses` / `_request_anthropic` 已分别处理）。

### 4.3 ❗**长报告 token 上限会被自动砍到 1/4**

`scan.py:2754-2755`：
```python
live_model = os.environ.get("CLAWSOCKET_LIVE_MODEL", "")
report_max_tokens = 8000 if live_model.lower().startswith(("claude-", "anthropic/")) else 30000
```
`live_probe()` 成功后会写 `CLAWSOCKET_LIVE_MODEL`。**一旦切到 opus，scan 的 HTML 报告上限从 30000 → 8000**。

这是 V16 修 524 超时时刻意加的（见 `CLAWSOCKET_V16_CHANGELOG.md` 第 6 条），不算 bug，但**报告会被截断**，需评估是否可接受（或调整阈值）。同理 `review.py:3603` 写死 `max_tokens=30000`，切 Claude 后同样是 524/截断高发区——**建议一并下调**。

### 4.4 输出格式 / JSON 解析漂移

`scan.py:2792` 注释已经记录了「gpt-6-astra 输出格式漂移」的历史（评分不再固定带 `/100`）。换模型后：
- 评分/结论的文本格式可能再变（如改带 `**加粗**`、不同分隔习惯）。
- 解析器 `_extract_json_object`（scan.py:2188）是**容错**的（找第一个平衡 `{}`，容忍 ```json 围栏），JSON 部分问题不大。
- 但**正则/字符串匹配的解析**（如 `分析评分` 抽取、`评分:78分`）是脆弱点，切换后**必须实跑一次 scan 并肉眼核对输出**。

### 4.5 测试

- `tests/test_fetch_news.py:193` 硬断言 `model == "gpt-6-astra"` → **必改**，否则 221 → 220 失败。
- 其余 220 个测试不依赖模型名（都是 mock/local 逻辑），不受影响。

### 4.6 成本/速率

ClawSocket 是**中转站**，GPT 与 Claude **共用同一份余额**（`ai_router.py` docstring 明确说了）。把主分析也切到 opus：
- 单价通常高于 GPT 系列，scan 单次 4 次调用（12000/3000/30000→8000/10000 tokens）+ review 30000 + evolve 红队，**成本会明显上升**。
- 速率限制未见代码约束，但切换后需盯紧 429。

---

## 5. 建议改法：环境变量 vs 硬编码

### 建议：**环境变量优先（保留代码默认），但先把硬编码处补上 env 覆盖**

| 场景 | 建议 |
|---|---|
| `review.py:50`（当前硬编码） | **改成 `os.environ.get("GPT_MODEL") or "claude-opus-5-5"`** —— 与 scan/evolve/fetch_news 口径统一 |
| `scan.py:62` / `evolve.py:17` / `fetch_news.py:61` | 只改**默认值**，`os.environ.get("GPT_MODEL") or ...` 结构保留 |
| `clawsocket_compat.py:91` 的 GPT fallback 列表 | **保留** `gpt-6-astra` 等 GPT 备用（万一 opus 挂了还有退路），只调整业务侧默认值 |
| `ai_router.py:20` | 一致性改（该文件未被引用，零风险） |

### 两种落地路径（二选一）

**路径 A：改代码默认值**（推荐，最省事）
- 改 4 个默认值（`review.py:50` 顺带补 env 覆盖）+ 1 个测试断言。
- 优点：无需碰 workflow、无需配 Secret；缺点：再换模型要再发一次代码。

**路径 B：只配环境变量（改 workflow）**
- 在 `scan.yml` / `review.yml` / `evolve.yml` / `news-fetch.yml` 的 env 段各加一行 `GPT_MODEL: claude-opus-5-5`。
- 优点：以后换模型只改 workflow；缺点：`review.py:50` 硬编码**不读 env**，路径 B 对它无效（仍需先改代码）。

### 🔒 无论选哪条，落地前必须先做三件事

1. **用 `/v1/models` 确认准确 ID**（本地做不了，需在 CI 或用 `clawsocket_probe.py`）。
2. **补上 `_looks_like_model_route_error` / `_runtime_fallback_candidates`**，或把 `clawsocket_compat.py:324-343` 整段包 `try/except` —— 否则切换失败时是崩溃，不是降级。
3. **先改 `review.py:50` 支持 env**，否则路径 B 对它无效。

### 建议的灰度顺序（降低爆炸半径）

1. 先只切 **`dashboard/fetch_news.py`**（新闻翻译，30 条/轮、失败静默、R1 兜底，**炸了也不影响交易链路**）→ 观察 1-2 轮 cron。
2. 再切 **`evolve.py:17`**（每月才跑一次，且已有 `claude-opus-5` 红队在跑，Claude 侧已被验证可用）。
3. 最后切 **`scan.py` + `review.py`**（交易主链路，且要处理 4.3 的 30000→8000 截断问题）。

---

## 附：速查

| 项 | 值 |
|---|---|
| 当前 GPT 主模型 | `gpt-6-astra`（scan/review/evolve/news 四处默认） |
| 已在跑的 Claude 模型 | `claude-opus-5`（evolve 红队审计，evolve.py:318） |
| 目标（待确认） | 「opus 5.5」→ 推测 `claude-opus-5-5` |
| 唯一硬编码处 | `review.py:50` |
| 会红的测试 | `tests/test_fetch_news.py:193` |
| workflow 注入模型变量 | **无**（scan/review/evolve/news-fetch 只注入 `CLAWSOCKET_API_KEY` + `CLAWSOCKET_BASE_URL`） |
| 潜伏 bug | `clawsocket_compat.py:324/326` 调用两个未定义方法 |
