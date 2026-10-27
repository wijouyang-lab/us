# 市场情绪 AI 解读 · 数据契约

「📊 市场情绪指标」板块（CNN 恐惧贪婪 + CME FedWatch）的数据抓取是**纯数据**：
`dashboard/fetch_market_indicators.py` 只抓行情/概率，**不调用任何 AI**。

AI 解读由独立的生成器写入下面这个文件，Dashboard 只读展示：

```
dashboard/data/market_ai_commentary.json
```

## 谁生成

`dashboard/market_ai_commentary.py` + `.github/workflows/market-ai-commentary.yml`：

- 每个交易日 **22:40 UTC**（≈ 美东 18:40）自动运行一次，也可在 Actions 里手动 `workflow_dispatch`；
- 只读取 `market_indicators.json`，把数据交给 ClawSocket（`ai_router.gpt_generate_text`）生成中文解读；
- 模型输出必须是 JSON（`summary` + `sections`），解析失败则**保留旧文件**、退出码 1；
- 未配置 `CLAWSOCKET_API_KEY/BASE_URL` → 脚本跳过（exit 0），前端继续显示 pending；
- 无指标数据（文件缺失/为空）→ 跳过，不写文件。

也可以手工写入同结构 JSON（例如复盘时补充人工观点）。

## 文件不存在时

前端显示一行占位：

> 🤖 AI 解读 pending · 等待外部研究写入 `market_ai_commentary.json`（本页不调用 AI）

不会报错、不会显示空白卡片、也不会编造内容。

## Schema（v1）

```json
{
  "generated_at": "2026-10-27T00:00:00Z",
  "model": "gpt-x",
  "summary": "整体情绪偏恐慌，但尚未到极端；FedWatch 显示 10 月按兵不动概率 88.9%。",
  "sections": [
    { "title": "恐惧贪婪结构", "text": "六个子项全部处于恐惧区间，其中股价强度与看跌/看涨期权为极度恐惧。" },
    { "title": "利率预期", "text": "下次 FOMC hold 概率 88.9%，12 月加息 25bp 概率 72.8%。" }
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `generated_at` | ISO8601 / null | 否 | 生成时间（原样展示） |
| `model` | string / null | 否 | 生成模型（原样展示） |
| `summary` | string / null | 否 | 一段总述 |
| `sections[]` | array | 否 | 分节解读，最多展示 10 段 |
| `sections[].title` | string / null | 否 | 小节标题 |
| `sections[].text` | string | **是** | 正文；为空的分节会被丢弃 |

- 文本按纯文本渲染（会做 HTML 转义），不解析 Markdown/HTML。
- 文件损坏或结构不是对象 → 后端返回 `null`（前端退回 pending），不影响 F&G / FedWatch 数据。

## 边界

1. 导出层（`dashboard_export._read_market_ai`）**只读透传**，不调用 AI、不生成文案。
2. 与 Quant Phase 1–7、$50,000 账本完全无关。
3. 谁生成谁负责：模型、时效、免责声明由写入方（GPT/量化）决定。
