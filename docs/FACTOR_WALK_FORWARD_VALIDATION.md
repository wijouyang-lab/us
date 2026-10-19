# BP 因子 Walk-Forward 滚动验证 + 测试段构成诊断

> 脚本：`tools/research/factor_walk_forward.py`
> 数据：`research_fundamentals_pit_corrected.csv`；因子 **`BP`**（行业中性化排序）；前瞻 **20D**
> 样本：**1973** 观测，2025-06-29 ~ 2026-11-29
> 窗口：训练 **6** 月 / 测试 **3** 月 / 步长 **3** 月；**实际可用窗口 3 个**（受样本跨度限制，未达 12 个）

## 1. 行业构成诊断（训练 vs 测试，%）

| Sector | 训练段 | 测试段 | 差值 |
|---|---|---|---|
| Information Technology | 15.1 | 18.1 | +3.0 |
| Industrials | 16.5 | 15.8 | -0.7 |
| Financials | 15.1 | 13.9 | -1.2 |
| Health Care | 11.6 | 11.8 | +0.2 |
| Consumer Discretionary | 9.0 | 9.1 | +0.1 |
| Consumer Staples | 6.9 | 7.9 | +1.0 |
| Utilities | 6.5 | 5.8 | -0.7 |
| Real Estate | 6.0 | 5.4 | -0.6 |
| Materials | 4.6 | 4.4 | -0.2 |
| Energy | 4.3 | 4.0 | -0.3 |
| Communication Services | 4.3 | 3.9 | -0.4 |

**测试段最大 Sector：`Information Technology` 占 **18.1%** ⇒ 未见行业集中（≤30%）**

### BP 极端值（P95 以上）的行业分布（%）

| 段 | Sector | 占比 |
|---|---|---|
| test | Financials | 50.0 |
| test | Health Care | 13.6 |
| test | Energy | 9.1 |
| test | Real Estate | 4.5 |
| test | Utilities | 4.5 |
| test | Consumer Discretionary | 4.5 |
| test | Information Technology | 4.5 |
| test | Communication Services | 4.5 |
| test | Consumer Staples | 4.5 |
| train | Financials | 42.9 |
| train | Materials | 11.7 |
| train | Consumer Discretionary | 9.1 |
| train | Health Care | 9.1 |
| train | Consumer Staples | 7.8 |
| train | Communication Services | 5.2 |
| train | Real Estate | 3.9 |
| train | Utilities | 3.9 |
| train | Energy | 2.6 |
| train | Industrials | 2.6 |
| train | Information Technology | 1.3 |

## 2. Walk-Forward 结果

| # | 训练段 | 测试段 | 方向 | 训练多空(%) | 训练t | 测试多空(%) | 测试t | IC | n |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2025-06~2025-12 | 2025-12~2026-03 | 多高BP | +1.986 | +1.47 | +0.686 | +0.36 | +0.0407 | 475 |
| 2 | 2025-09~2026-03 | 2026-03~2026-06 | 多高BP | +1.180 | +1.01 | -1.039 | -0.39 | -0.0659 | 476 |
| 3 | 2025-12~2026-06 | 2026-06~2026-09 | 多高BP | +0.149 | +0.09 | +1.806 | +1.26 | +0.1652 | 475 |

## 3. 汇总

- 窗口数：**3**
- 多空为正的窗口：**2/3**（67%）
- 平均多空：**+0.485%**（中位 +0.686%）
- 多空标准差：**1.433%**
- IC 均值：**+0.0466**，IC 标准差：**0.1156**
- **ICIR = 0.403**

### 判定：**✗ 不稳定**
- 判据：方向一致窗口 > 2/3（需 >2.0）且 ICIR > 0.3
- 实际：2/3 窗口为正、ICIR=0.403

## 4. 限制

1. 样本仅 ~16 个月 ⇒ **实际窗口数远少于 12**，统计效力有限。
2. 每窗口测试集观测数小（~60-150）⇒ t/IC 噪声大。
3. 未扣成本；未做多重检验校正。
