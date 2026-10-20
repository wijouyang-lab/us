# 行业轮动因子侦察（最强 vs 最弱 Sector）

> 脚本：`tools/research/sector_rotation_recon.py`
> 样本：**482** 行 / **5** 个 Scan_Date / **11** 个 Sector
> 排序依据：每日按 `Sector_RS_20D_Pct` 的 Sector 内均值排序，取前 3 强 / 后 3 弱
> ⚠️ **数据边界**：`Forward_Return_5D` 非空 1342 行；**10D 仅 5 行、20D 全空** ⇒ **5D 是唯一可结论的期限** ✓

## 1. 最强 vs 最弱 Sector（个股等权）

| 组合 | 期限 | 平均收益 | 胜率 | 样本数 |
|---|---|---|---|---|
| **最强 3 Sector** | 5D | **-1.965%** | 45.5% | 224 |
| **最强 3 Sector** | 10D | **+nan%** | nan% | 0 |
| **最弱 3 Sector** | 5D | **-0.490%** | 49.5% | 99 |
| **最弱 3 Sector** | 10D | **+nan%** | nan% | 0 |
| 全市场基准 | 5D | **-0.766%** | 54.8% | 482 |
| 全市场基准 | 10D | **+nan%** | nan% | 0 |

## 2. 核心对比（5D）

- **最强 3 Sector**：-1.965%（胜率 45.5%，n=224）
- **最弱 3 Sector**：-0.490%（胜率 49.5%，n=99）
- **多空差（强 − 弱）**：**-1.474 pp** ✗ 方向相反
- **全市场基准**：-0.766%（胜率 54.8%，n=482）
- **强势超额（强 − 全市场）**：**-1.198 pp**

## 3. 每日强弱 Sector 明细

| Scan_Date | 最强 3 | 最弱 3 | 当日股票数 |
|---|---|---|---|
| 2026-10-07 | Technology, Healthcare, Communication | Materials, Real Estate, Financials | 70 |
| 2026-10-08 | Technology, Healthcare, Consumer Staples | Utilities, Real Estate, Financials | 69 |
| 2026-10-09 | Technology, Healthcare, Energy | Materials, Real Estate, Financials | 137 |
| 2026-10-12 | Technology, Healthcare, Energy | Materials, Real Estate, Financials | 136 |
| 2026-10-13 | Technology, Healthcare, Energy | Real Estate, Communication, Financials | 70 |

## 4. ⚠️ 限制（必读）

1. **仅 5D 可结论** ✗ —— 10D 只有 5 行、20D 为 0（价格历史未覆盖足够前瞻）✓
2. **仅 9 个 Scan_Date** ⇒ 重叠偏差严重，**统计量不可当稳健结论** ✓
3. `Sector_RS_20D_Pct` 本身是**过去 20 日**的相对强度 ⇒ 该检验是「**动量延续**」检验 ✓
4. 未扣成本；未做行业市值加权（**个股等权** ✓）
5. 未区分 `market_regime`（牛/熊市中轮动效应可能反转）✓

## 5. 判读

- **方向不支持行业轮动**（强 − 弱 = -1.474 pp）✗
- **强势超额** -1.198 pp ⇒ **选强行业无用** ✗
- **任一 |差| < 0.5 pp 时，在 n<1000、9 个日期的条件下基本是噪声** ✗
