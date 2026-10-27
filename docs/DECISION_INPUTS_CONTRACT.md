# 决策输入快照 · 契约

`dashboard/data/decision_inputs.json` 由 `dashboard/build_decision_inputs.py` 生成。
它把各板块压缩成**只读、可审计**的特征，供量化研究（GPT）定义权重/阈值后使用。

## 原则

- 只聚合，不做加权、不打分、不产生买卖信号；
- 每个特征带 `status`：`ok` / `partial` / `missing`；缺失写 `null`，绝不补 0；
- 生成时间 `generated_at`，数据截止 `asof`。

## Schema

```json
{"schema":1,"generated_at":"...","asof":"...",
 "note":"只读决策输入快照：权重/阈值/买卖规则由量化研究定义，本层不做判断。",
 "features":[{"key":"cpi_yoy_surprise","label":"CPI预期差","group":"宏观",
              "value":0.1,"unit":"pp","status":"ok","source":"macro_forecast"}]}
```

## 当前特征

| group | key | 含义 |
|---|---|---|
| 宏观 | macro_ok / macro_missing | 有值项 / 缺失项 |
| 宏观 | cpi_yoy_surprise / core_cpi_yoy_surprise / unrate_surprise / cpi_mom_surprise | 实际−预期（pp） |
| 情绪 | fg_score | CNN 恐惧贪婪 |
| 情绪 | fed_hold | 最近会议按兵不动概率 |
| 超跌 | oversold_count / oversold_rsi | 候选数 / 平均 RSI |
| 供应链 | serenity_top / serenity_verified | 研究优先级数 / 已核验数 |
| 新闻 | news_bull / news_bear | 利好/利空条数 |
| 新闻 | speaker_bear | 讲话利空条数 |

## 接入策略

策略读取该 JSON 后如何使用（权重、阈值、门控）由 GPT 的量化研究定义；
本仓库只保证数据口径、时间戳与 fail-closed 行为。
