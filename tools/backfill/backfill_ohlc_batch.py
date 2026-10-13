# -*- coding: utf-8 -*-
"""分批回填 OHLCV（重试版，区别于原 backfill_ohlc.py）。

- 读取真实 CSV（8 列：Date/Ticker/Open/High/Low/Close/Volume/schema_version）。
- 每批 20 个 ticker 用 yfinance 拉 2026-09-27~2026-10-08 的 OHLCV（auto_adjust=False，与模块口径一致）。
- 批间 sleep 3 秒，避免再次触发 429 限流。
- 仅填充 O/H/L/V；Close 沿用 CSV 原值，绝不覆盖。
- schema_version 保持原值（phase2b.v1），不升 v2，与 quant_factor_price.py 常量一致。
- 单批拉取异常不影响其它批（该批记为未填），最终报告 filled / unfilled。

铁律：纯 /tmp 临时脚本，不进仓库、不 push、不碰监控、不改任何仓库 .py。
"""
import sys
import time
import pandas as pd

PATH = "/tmp/us/quant_factor_price_history.csv"
BATCH = 20
SLEEP = 3.0

df = pd.read_csv(PATH, dtype=str, keep_default_na=False)
for c in ["Open", "High", "Low", "Volume"]:
    if c not in df.columns:
        df[c] = ""
df["schema_version"] = df.get("schema_version", "phase2b.v1")

tickers = sorted(df["Ticker"].unique())
dates = sorted(df["Date"].unique())
min_d, max_d = dates[0], dates[-1]
end = (pd.Timestamp(max_d) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

print(f"[回填] tickers={len(tickers)} dates={min_d}..{max_d} (共 {len(dates)} 天, {len(df)} 行)")
print(f"[回填] 分批: 每批 {BATCH} ticker, 批间 sleep {SLEEP}s")

import yfinance as yf


def fetch_batch(batch):
    """返回 {(ticker, date_str): {Open,High,Low,Volume}} 或 None。"""
    try:
        data = yf.download(batch, start=min_d, end=end, auto_adjust=False,
                           progress=False, threads=False, group_by="ticker")
    except Exception as e:
        print(f"[回填][批失败] {batch[0]}..{batch[-1]} yf 异常: {type(e).__name__}: {e}")
        return None
    if data is None or (hasattr(data, "empty") and data.empty):
        return {}
    try:
        cols = data.columns
        multi = isinstance(cols, pd.MultiIndex)
    except Exception:
        multi = False
    out = {}
    for tk in batch:
        sub = data if (not multi and len(batch) == 1) else (data[tk] if (multi and tk in cols.get_level_values(0)) else None)
        if sub is None or (hasattr(sub, "empty") and sub.empty):
            continue
        idx = pd.to_datetime(sub.index, errors="coerce").tz_localize(None).normalize()
        for d in dates:
            mask = idx == pd.Timestamp(d).normalize()
            if not mask.any():
                continue
            r = sub.loc[mask].iloc[0]
            ohlv = {}
            for c in ["Open", "High", "Low", "Volume"]:
                if c in sub.columns:
                    v = r[c]
                    if v is not None and not pd.isna(v):
                        ohlv[c] = int(round(float(v))) if c == "Volume" else round(float(v), 6)
            if ohlv:
                out[(tk, d)] = ohlv
    return out


filled = 0
unfilled = 0
batch_n = (len(tickers) + BATCH - 1) // BATCH

for bi in range(batch_n):
    batch = tickers[bi * BATCH:(bi + 1) * BATCH]
    print(f"[回填] 批 {bi + 1}/{batch_n} tickers={batch[0]}..{batch[-1]} ({len(batch)})")
    lut = fetch_batch(batch)
    if lut is None:  # 整批异常
        unfilled += len(batch) * len(dates)
        if bi < batch_n - 1:
            time.sleep(SLEEP)
        continue
    # 标记本批是否整批拉空（yfinance 限流可能返回空 DataFrame 而非异常）
    if len(lut) == 0:
        print(f"[回填][批警告] 批 {bi + 1} 返回 0 行（可能限流），整批标记未填")
        unfilled += len(batch) * len(dates)
        if bi < batch_n - 1:
            time.sleep(SLEEP)
        continue
    for i, row in df.iterrows():
        if row["Ticker"] not in batch:
            continue
        if str(row.get("Open", "")).strip() not in ("", "nan") and str(row.get("High", "")).strip() not in ("", "nan"):
            continue  # 已填跳过
        ohlv = lut.get((row["Ticker"], row["Date"]))
        if not ohlv:
            unfilled += 1
            continue
        changed = False
        for c in ["Open", "High", "Low", "Volume"]:
            if c in ohlv:
                df.at[i, c] = ohlv[c]
                changed = True
        if changed:
            filled += 1
        else:
            unfilled += 1
    if bi < batch_n - 1:
        time.sleep(SLEEP)

df.to_csv(PATH, index=False, encoding="utf-8")
print(f"[回填] 完成：filled={filled} unfilled={unfilled} total={len(df)}")
print(f"[回填] schema_version 分布: {df['schema_version'].value_counts().to_dict()}")
