# -*- coding: utf-8 -*-
"""【代码集成验证专用 · 合成数据 · 非实验结论 · 非证据】

仅用于在沙箱 yfinance 被限流、本地又无 10y 行情时，验证 4 个实验脚本与仓库因子函数
能正确串起来并产出 IC / 五分位 / 组合指标格式。

数据特征：价格由"温和 AR(1) 动量因子 + 噪声"驱动，使过去 20 日动量与该标的
未来收益存在弱正相关（Momentum_20D_Pct 呈正 IC），仅用于演示指标 machinery。
绝不作为"技术因子 OOS 有效"的任何结论依据。
"""
import os

import numpy as np
import pandas as pd

np.random.seed(42)
TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "SPY"]
START = pd.Timestamp("2021-01-04")
N = 504  # ~2 年交易日
DATES = pd.bdate_range(START, periods=N)

rows = []
for t in TICKERS:
    rng = np.random.default_rng(abs(hash(t)) % (2**32))
    m = np.zeros(N)
    for i in range(1, N):  # AR(1) 动量因子，有界
        m[i] = 0.95 * m[i - 1] + 0.1 * rng.standard_normal()
    # 日收益 = 动量信号 + 噪声（有界，保证价格有限为正）
    r = 0.05 * m + rng.normal(0, 0.015, N)
    r = np.clip(r, -0.5, 0.5)
    closes = 100.0 * np.cumprod(1.0 + r)
    for i, d in enumerate(DATES):
        c = float(closes[i])
        o = c * (1 + rng.normal(0, 0.003))
        hi = max(o, c) * (1 + abs(rng.normal(0, 0.004)))
        lo = min(o, c) * (1 - abs(rng.normal(0, 0.004)))
        v = int(rng.integers(1_000_000, 5_000_000))
        rows.append({
            "Date": d, "Ticker": t, "Open": round(o, 2), "High": round(hi, 2),
            "Low": round(lo, 2), "Close": round(c, 2), "Adj Close": round(c, 2),
            "Volume": v,
        })

df = pd.DataFrame(rows)
os.makedirs("/tmp/experiment", exist_ok=True)
df.to_csv("/tmp/experiment/history.csv", index=False)
print(f"[synthetic] 生成 {len(df)} 行（{len(TICKERS)} 只 × {N} 日），写入 history.csv")
