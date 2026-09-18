# US Scan v9 — 运行日志后续修复

根据 2026-09-17/18 运行日志追加三项修复：

1. **Claude 持仓风控 JSON 解析更稳**：改用括号深度解析，容忍 ```json 包裹、前后解释和字符串中的花括号。解析失败仍安全保留 Active，不把持仓误 Drop。
2. **SPY 跌破 MA20 不再在 NORMAL + 浅回撤时一刀切**：只有 VIX 进入 STRESSED/PANIC，或 SPY 近5日跌幅达到参数硬阈值（默认 -2%）时，才对非防御行业执行硬阻断；正常浅回撤改为 Risk/Liquidity 轻微扣分。
3. **硬门槛增加失败原因分布**：下一次日志会输出 TECH_FAIL / QUANT_FAIL / ATR_FAIL / SECTOR_RS_FAIL / SPY_TREND_FAIL / PANIC_FAIL 各多少只，便于判断到底是哪一层太严。
4. **期权 Delta/IV 数据一致性**：使用实际 DTE 计算 Delta；异常极小/异常 IV 不再参与 Black-Scholes Delta，避免出现 `IV=N/A` 但 `Delta=1.0` 的矛盾。

本次不修改 Historical CSV，不降低 Core=65 / Observation=58，也不修改止损参数。先观察新的真实候选数量和失败原因，再根据至少一段新样本决定是否继续调门槛。
