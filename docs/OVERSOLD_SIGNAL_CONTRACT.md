# 超跌观察候选 · 数据契约

本文件定义 Dashboard「超跌观察推荐」板块的**唯一数据源**。Dashboard 只负责展示，
**不计算**任何超跌分数、阈值或买卖信号；策略与回测由外部研究（GPT / 量化）负责。

## 文件位置

```
dashboard/data/oversold_candidates.json
```

- 文件不存在 → Dashboard 板块**整块隐藏**（fail-closed，与 `skill_serenity` / `market_indicators` 一致）。
- 文件存在但 `candidates` 为空 → 板块显示「暂无超跌候选」空态。
- 文件损坏/结构错误 → 板块隐藏（后端记 WARN，不影响其它板块）。

## Schema（v1）

```json
{
  "schema": 1,
  "generated_at": "2026-10-26T18:00:00Z",
  "asof": "2026-10-24",
  "source": "GPT 量化研究",
  "note": "本周超跌反弹候选，非生产信号",
  "candidates": [
    {
      "ticker": "XYZ",
      "name": "XYZ Inc",
      "score": 82.5,
      "tag": "超跌反弹",
      "rsi": 22.4,
      "bias_pct": -14.2,
      "drawdown_pct": -28.5,
      "ref_price": 95.2,
      "stop_loss": 88.5,
      "confirm": "RSI 回升过 30 + 缩量后首次放量阳线",
      "invalid": "跌破前低 $88.50 或财报指引下修",
      "observe_until": "2026-11-05",
      "reason": "板块未同步下跌，个股跌因一次性事件；估值回到 5 年 10% 分位。"
    }
  ]
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `schema` | int | 否 | 契约版本，当前 `1` |
| `generated_at` | ISO8601 / null | 否 | 信号生成时间 |
| `asof` | `YYYY-MM-DD` / null | 否 | 数据截止交易日 |
| `source` | string / null | 否 | 信号来源（如「GPT 量化研究」） |
| `note` | string / null | 否 | 顶部说明 |
| `candidates[].ticker` | string | **是** | 必填，缺失的条目会被丢弃 |
| `candidates[].name` | string | 否 | 公司名 |
| `candidates[].score` | number | 否 | 超跌分（口径由外部研究定义） |
| `candidates[].tag` | string | 否 | 如「超跌反弹」「错杀」 |
| `candidates[].rsi` | number | 否 | RSI14 |
| `candidates[].bias_pct` | number | 否 | 相对 MA20 偏离（%） |
| `candidates[].drawdown_pct` | number | 否 | 回撤（%），负值 |
| `candidates[].ref_price` | number | 否 | 参考价 |
| `candidates[].stop_loss` | number | 否 | 参考止损位 |
| `candidates[].confirm` | string | 否 | 右侧确认条件 |
| `candidates[].invalid` | string | 否 | 失效条件 |
| `candidates[].observe_until` | `YYYY-MM-DD` | 否 | 观察到期日 |
| `candidates[].reason` | string | 否 | 入选理由 |

- 最多展示 20 条（按文件顺序）。
- 缺失/非数字字段显示为 `—`，绝不补 0。
- `candidates` 之外的字段只做展示，不参与任何计算。

## 边界（重要）

1. 板块标题带「非生产信号 · 仅供观察」，不进入 `$50,000` 账本、不产生买卖。
2. 本板块与 Quant Phase 1–7 板块**完全独立**，不修改、不依赖量化模块。
3. 阈值、权重、回测、仓位与止损方式均由外部研究决定；Dashboard 不内置任何超跌规则。

## CSV → JSON 转换脚本

外部研究通常更方便产出 CSV。仓库提供一个**纯格式转换**脚本（不含任何筛选/打分逻辑）：

```bash
# 预览（不写文件）
python scripts/oversold_csv_to_json.py candidates.csv --dry-run \
  --asof 2026-10-24 --source "GPT 量化研究"

# 正式写入（默认 dashboard/data/oversold_candidates.json）
python scripts/oversold_csv_to_json.py candidates.csv \
  --asof 2026-10-24 --source "GPT 量化研究" \
  --note "本周超跌候选（非生产信号）"
```

CSV 表头可用英文或中文（大小写、空格、下划线、括号、百分号不敏感）：

```csv
ticker,name,score,tag,rsi,bias_pct,drawdown_pct,ref_price,stop_loss,confirm,invalid,observe_until,reason
XYZ,XYZ Inc,82.5,超跌反弹,22.4,-14.2,-28.5,$95.20,$88.50,RSI 回升过 30,跌破 $88.50,2026-11-05,板块未同步下跌
```

等价中文表头：

```csv
代码,名称,超跌分,标签,RSI,偏离,回撤,参考价,止损,确认条件,失效条件,观察至,理由
```

行为约定：

- 只做列名映射、`$`/`,`/`%`/unicode 负号清洗、ticker 大写；**缺失字段写 `null`，绝不补 0**；
- `ticker` 为空的行直接跳过，并在 stderr 汇总（前 10 行明细）；
- 无法识别的列会在 stderr 告警，随后忽略；
- 0 条有效候选默认报错退出（防止误清空线上数据），确需清空时加 `--allow-empty`；
- `--dry-run` 只打印 JSON；正式写入使用「临时文件 + 原子替换」。

