# 宏观数据「预期 vs 实际」· 数据契约

Dashboard 的「📊 宏观板块」新增一块 **「🎯 预期 vs 实际」**，用来展示
**分析师一致预期（consensus）与实际公布值**的差距，并解释这个差距对市场的含义。

> 分工：Quant / 量化研究归 GPT；宏观数据与展示由本仓库维护。

## 文件位置

```
dashboard/data/macro_forecast.json
```

- 文件不存在 → 板块**隐藏**（fail-closed）；
- 文件存在但 `items` 为空 → 不显示该块；
- 文件损坏 → 不显示，不影响其它宏观数据。

导出层（`dashboard_export._read_macro_forecast`）只做透传，并计算：

```
surprise = actual − forecast   （单位：百分点 pp）
```

**不抓日历、不推断一致预期、不调用 AI**。数据由维护者从财经日历核对后写入。

## Schema（v1）

```json
{
  "schema": 1,
  "generated_at": "2026-10-27T06:30:00Z",
  "as_of": "2026-10-26",
  "source": "财经日历（金十数据，截图核对）",
  "items": [
    {
      "indicator": "核心PCE物价指数",
      "period": "2026 Q2 · 年化季率终值",
      "forecast": 3.6,
      "actual": 3.3,
      "previous": 3.6,
      "unit": "%",
      "released_at": "2026-09-30",
      "impact": "低于预期 0.3pp：核心通胀降温 → 12 月加息概率下修，短端美债收益率与美元承压，利好久期/成长资产与黄金。"
    }
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `indicator` | string | **是** | 指标名（如 核心PCE物价指数） |
| `forecast` | number | **是** | 一致预期值；缺该字段的条目会被丢弃 |
| `actual` | number | **是** | 实际公布值；缺该字段的条目会被丢弃 |
| `previous` | number | 否 | 前值 |
| `unit` | string | 否 | 默认 `%` |
| `period` | string | 否 | 数据期间/口径（**必须写清口径**，如「季率终值」） |
| `released_at` | `YYYY-MM-DD` | 否 | 公布日 |
| `impact` | string | 否 | 预期差的市场含义（纯文本描述，不构成建议） |

顶层：`schema / generated_at / as_of / source`，`items` 最多展示 30 条。

## 展示规则

- 标题：指标名 + 口径（period）+ 公布日
- 数值：`预期 3.60% ｜ 实际 3.30% ｜ 差值 -0.30pp ｜ 低于预期`
- 方向阈值：`|surprise| ≤ 0.05` 视为「符合预期」；否则高于/低于预期
- 颜色：高于=红、低于=绿（仅表示方向，不代表好坏）；`impact` 文本解释实际含义

## 维护约定

1. 只在**官方公布之后**写入 `actual`，预期值来自公布前的财经日历，并记录 `source`。
2. 不同口径要分行（例如「核心PCE 月度同比 3.0%」与「核心PCE 年化季率终值 3.3%」是两条，不能合并）。
3. 不写没有来源的预期值；拿不到一致预期就不写该行。

## 人工维护预期（免费兜底）

自动抓取拿不到一致预期时（如非农），可在 `dashboard/data/macro_forecast_manual.json`
手工写入，合并时**人工值优先**：

```json
{"items":[{"key":"nonfarm","indicator":"季调后非农","forecast":50,"unit":"K",
  "period":"2026年10月","source":"manual"}]}
```

- `key` 必须与 macro_indicators 对齐（nonfarm / claims / adp / cpi_yoy /
  core_cpi_yoy / cpi_mom / unrate / umich / ism / eia_crude_chg）；
- 实际值仍由 macro_indicators 覆盖，AI 解读照常生成；
- 文件缺失或 items 为空 → 不影响自动抓取结果。
