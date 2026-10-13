# -*- coding: utf-8 -*-
"""一次性回填：把现有仅含 Close 的 price_history 升到 OHLCV 并补采历史 O/H/L/V。

- 读取真实 CSV，补到 8 列（Open/High/Low/Volume 先留空）。
- yfinance 拉全量 ticker 在 [最早, 最晚+1] 区间的 OHLCV（auto_adjust=False，与模块口径一致）。
- 仅填充 O/H/L/V；Close 沿用已校验值，不覆盖。
- 回填成功的行 schema_version 升到 phase2b.v2；拉不到的行保持空 + v1。
- 无论如何重写 CSV 到新 8 列 schema（即使全失败，结构也对齐，新数据自然补采）。
"""
import os
import sys
import pandas as pd
import numpy as np

sys.path.insert(0, "/tmp/us")
from quant_factor_price import PRICE_HISTORY_COLUMNS, SCHEMA_VERSION

PATH = "/tmp/us/quant_factor_price_history.csv"
TARGET_VERSION = "phase2b.v2"

df = pd.read_csv(PATH, dtype=str, keep_default_na=False)
# 升到 8 列
for c in ["Open", "High", "Low", "Volume"]:
    if c not in df.columns:
        df[c] = ""
df = df[PRICE_HISTORY_COLUMNS]

tickers = sorted(df["Ticker"].unique())
dates = sorted(df["Date"].unique())
min_d, max_d = dates[0], dates[-1]
end = (pd.Timestamp(max_d) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

print(f"[回填] tickers={len(tickers)} dates={min_d}..{max_d} (共 {len(dates)} 天, {len(df)} 行)")

try:
    import yfinance as yf
    print("[回填] yfinance 可用，拉取 OHLCV ...")
    data = yf.download(tickers, start=min_d, end=end, auto_adjust=False,
                       progress=False, threads=True, group_by="ticker")
    print("[回填] yfinance 返回完成")
except Exception as e:
    print(f"[回填][失败] yfinance 拉取异常：{type(e).__name__}: {e}")
    print("[回填] 按约定留空 O/H/L/V，仅重写结构（新数据将自然补采）")
    df.to_csv(PATH, index=False, encoding="utf-8")
    print(f"[回填] 已重写 {len(df)} 行到 8 列 schema（O/H/L/V 为空）")
    sys.exit(0)

OHLCV = ["Open", "High", "Low", "Close", "Volume"]


def lookup(t, d):
    try:
        sub = data if len(tickers) == 1 else (data[t] if t in data.columns.get_level_values(0) else None)
        if sub is None or sub.empty:
            return None
        idx = pd.to_datetime(sub.index, errors="coerce").tz_localize(None).normalize()
        mask = idx == pd.Timestamp(d).normalize()
        if not mask.any():
            return None
        r = sub.loc[mask].iloc[0]
        return {c: r[c] for c in OHLCV if c in sub.columns}
    except Exception:
        return None


filled = 0
unfilled = 0
for i, row in df.iterrows():
    if str(row.get("Open", "")).strip() not in ("", "nan") and str(row.get("High", "")).strip() not in ("", "nan"):
        continue  # 已填，跳过
    ohlcv = lookup(row["Ticker"], row["Date"])
    if ohlcv is None:
        unfilled += 1
        continue
    changed = False
    for c in ["Open", "High", "Low", "Volume"]:
        v = ohlcv.get(c)
        if v is not None and not pd.isna(v):
            df.at[i, c] = int(round(float(v))) if c == "Volume" else round(float(v), 6)
            changed = True
    if changed:
        df.at[i, "schema_version"] = TARGET_VERSION
        filled += 1
    else:
        unfilled += 1

df = df[PRICE_HISTORY_COLUMNS]
df.to_csv(PATH, index=False, encoding="utf-8")
print(f"[回填] 完成：filled={filled} unfilled={unfilled} total={len(df)}")
print(f"[回填] schema_version 升 v2 行数 = {(df['schema_version']==TARGET_VERSION).sum()}")
