# 美股宏观九项指标 · 数据契约

`dashboard/data/macro_indicators.json` 由 `dashboard/fetch_macro_indicators.py` 生成。
Dashboard 只读展示，不计算任何指标。

## 数据源

| key | 指标 | 主源 | 兜底 |
|---|---|---|---|
| unrate | 美国失业率 | FRED UNRATE | TradingEconomics |
| nonfarm | 季调后非农业就业人口 | FRED PAYEMS（月增，K） | TradingEconomics |
| cpi_yoy | 未季调CPI年率 | FRED CPIAUCNS（同月同比） | TradingEconomics |
| cpi_mom | 季调后CPI月率 | FRED CPIAUCSL（环比） | TradingEconomics |
| umich | 密歇根消费者信心终值 | FRED UMCSENT | TradingEconomics |
| ism | ISM制造业PMI | ISM 官网 | TradingEconomics |
| adp | ADP就业人数 | FRED ADPMNUSNERSA（月增，K） | TradingEconomics |
| eia_crude | 每周EIA原油库存 | EIA 周报（千桶） | — |
| claims | 每周初请失业金人数 | FRED ICSA（K） | TradingEconomics |

## Schema

```json
{"schema":1,"generated_at":"...","source":"FRED + ISM + EIA","count":9,"ok":9,
 "items":[{"key":"unrate","name":"美国失业率","value":4.2,"unit":"%",
           "date":"2026-09-01","prev":4.1,"change":0.1,
           "source":"FRED UNRATE","note":null}]}
```

- 逐项 fail-closed：抓不到写 `null`，前端显示「数据缺失」；
- `value` 为 `null` 时 `prev/change` 也必须为 `null`；
- 单位：`%`、`K`（千人）、`千桶`；
- 不改 quant_*、不进账本、不调用 AI。
