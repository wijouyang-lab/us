# 超跌观察候选 · 数据契约

本文件定义 Dashboard「超跌观察推荐」板块的**唯一数据源**。Dashboard 只负责展示，
**不计算**任何超跌分数、阈值或买卖信号。

数据由仓库内的**规则版生成器** `scripts/oversold_screen.py` 产生（只读
`quant_factor_snapshot.csv`，规则固定、未回测、不优化），也可以由外部研究通过
CSV 转换脚本覆盖写入。Quant Phase 1–7 的量化研究（GPT）与本板块完全独立。

## 文件位置

```
dashboard/data/oversold_candidates.json
```

- 文件不存在 → Dashboard 板块**整块隐藏**（fail-closed，与 `skill_serenity` / `market_indicators` 一致）。
- 文件存在但 `candidates` 为空 → 板块显示「暂无超跌候选」空态。
- 文件损坏/结构错误 → 板块隐藏（后端记 WARN，不影响其它板块）。

## 规则版生成器（默认数据来源）

```bash
python scripts/oversold_screen.py                 # 写 dashboard/data/oversold_candidates.json
python scripts/oversold_screen.py --dry-run       # 只打印，不落盘
python scripts/oversold_screen.py --max 10
```

固定规则（写死在脚本里，便于复核，**不是**调参后的策略）：

| 条件 | 阈值 |
|---|---|
| `RSI_14` | ≤ 32 |
| `Bias_Pct`（相对 MA20） | ≤ −8% |
| `ZScore_20D` | ≤ −1.5 |
| `Price` | ≥ $5 |
| `ATR_Pct` | 1.5% – 9% |
| `Volume_Ratio_20D` | ≥ 0.6 |

- 评分 = 0.4×RSI 深度 + 0.3×Bias 深度 + 0.3×ZScore 深度（仅排序用）
- `stop_loss` = `Price × (1 − min(12%, 1.5×ATR%))`，参考位，不是交易指令
- `drawdown_pct` 记录的是**近 20 日动量**（负值=下跌），面板标签为「20日」
- 快照缺失/为空 → 保留旧文件并退出 0（fail-closed）

## Schema（v1）

```json
{
  "schema": 1,
  "generated_at": "2026-10-26T18:00:00Z",
  "asof": "2026-10-24",
  "source": "规则筛选（RSI/Bias/ZScore + 流动性 + ATR）· 未回测 · 仅供观察",
  "note": "规则版观察信号：未做回测，不构成投资建议。",
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
      "confirm": "RSI 回升过 35 且站回 MA20 $98.40",
      "invalid": "跌破参考止损 $88.50 或 RSI 继续下行",
      "observe_until": "2026-11-05",
      "reason": "RSI 22.4 / Bias -14.2% / ZScore -2.4；ATR 4.2% · 20日量比 1.1。"
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
| `candidates[].drawdown_pct` | number | 否 | 近 20 日动量（%，负值；面板标签「20日」） |
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
3. 生成器只读 `quant_factor_snapshot.csv`，不写任何 `quant_*` 文件；规则固定、未回测，
   不宣称 alpha，也不作为投资建议。

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

