# -*- coding: utf-8 -*-
"""分批回填 OHLCV（stooq 数据源版；替换被 429 封锁的 yfinance）。

复用 backfill_ohlc_batch.py 的结构，仅替换数据源为 stooq：
- 读取真实 CSV（8 列：Date/Ticker/Open/High/Low/Close/Volume/schema_version）。
- 每批 20 个 ticker 用 stooq CSV 接口拉 2026-09-27~2026-10-08 的 OHLCV。
  URL: https://stooq.com/q/d/l/?s={ticker}.us&i=d&d1=20260927&d2=20261008
- 批间 sleep 1 秒（stooq 无严格限流）。
- 仅填充 O/H/L/V；Close 沿用 CSV 原值，绝不覆盖。
- schema_version 保持原值（phase2b.v1）。
- 单 ticker 拉取异常 / 命中反爬挑战页 → 该 ticker 整批标记未填；最终报告 filled / unfilled / failed_tickers。

铁律：纯 /tmp 临时脚本，不进仓库、不 push、不碰监控、不改任何仓库 .py。
注意：若运行环境出口 IP 被 stooq 反爬（返回 JS 验证页 / __verify 403），则所有 ticker 均会失败——
      此时本脚本如实报告 failed_tickers=全部，filled=0；需在未被封锁的 IP 上运行。
"""
import sys
import time
import requests
import pandas as pd

PATH = "/tmp/us/quant_factor_price_history.csv"
BATCH = 20
SLEEP = 1.0
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def _is_challenge(text: str) -> bool:
    """stooq 反爬：返回的是 JS 验证页而非 CSV。"""
    t = (text or "").lstrip()
    return t.startswith("<!DOCTYPE") or t.startswith("<html") or "requires JavaScript" in t


def fetch_ticker(tk: str, min_d: str, max_d: str):
    """逐 ticker 拉 stooq 日线 CSV，返回 {date_str: {Open,High,Low,Volume}} 或 None（失败/挑战）。"""
    sym = f"{tk.lower()}.us"
    d1 = pd.Timestamp(min_d).strftime("%Y%m%d")
    d2 = pd.Timestamp(max_d).strftime("%Y%m%d")
    url = f"https://stooq.com/q/d/l/?s={sym}&i=d&d1={d1}&d2={d2}"
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept": "text/csv,*/*"},
                         timeout=10)
    except Exception as e:
        print(f"[回填][{tk}] 请求异常: {type(e).__name__}: {e}")
        return None
    if r.status_code != 200:
        print(f"[回填][{tk}] HTTP {r.status_code}")
        return None
    if _is_challenge(r.text):
        print(f"[回填][{tk}] 命中 stooq 反爬验证页（IP 被封锁）")
        return None
    try:
        sub = pd.read_csv(pd.compat.StringIO(r.text.strip()))
    except Exception as e:
        print(f"[回填][{tk}] CSV 解析失败: {type(e).__name__}: {e}")
        return None
    if sub is None or sub.empty or "Date" not in sub.columns:
        return {}
    out = {}
    for _, row in sub.iterrows():
        d = pd.to_datetime(row.get("Date"), errors="coerce")
        if pd.isna(d):
            continue
        ds = d.strftime("%Y-%m-%d")
        ohlv = {}
        for c in ["Open", "High", "Low", "Volume"]:
            if c in sub.columns:
                v = row.get(c)
                if v is not None and not pd.isna(v):
                    ohlv[c] = int(round(float(v))) if c == "Volume" else round(float(v), 6)
        if ohlv:
            out[ds] = ohlv
    return out


def main():
    df = pd.read_csv(PATH, dtype=str, keep_default_na=False)
    for c in ["Open", "High", "Low", "Volume"]:
        if c not in df.columns:
            df[c] = ""
    df["schema_version"] = df.get("schema_version", "phase2b.v1")

    tickers = sorted(df["Ticker"].unique())
    dates = sorted(df["Date"].unique())
    min_d, max_d = dates[0], dates[-1]
    print(f"[回填] tickers={len(tickers)} dates={min_d}..{max_d} (共 {len(dates)} 天, {len(df)} 行)")
    print(f"[回填] 数据源=stooq  分批: 每批 {BATCH} ticker, 批间 sleep {SLEEP}s")

    filled = 0
    unfilled = 0
    failed_tickers = []

    batch_n = (len(tickers) + BATCH - 1) // BATCH
    for bi in range(batch_n):
        batch = tickers[bi * BATCH:(bi + 1) * BATCH]
        print(f"[回填] 批 {bi + 1}/{batch_n} tickers={batch[0]}..{batch[-1]} ({len(batch)})")
        batch_failed = False
        lut_all = {}
        for tk in batch:
            lut = fetch_ticker(tk, min_d, max_d)
            if lut is None:
                batch_failed = True
                failed_tickers.append(tk)
                # 该 ticker 所有日期标记未填
                unfilled += int((df["Ticker"] == tk).sum())
                continue
            # lut 可能是 {}（空结果，非失败）——不算 failed，但也不填
            lut_all[tk] = lut
        if batch_failed:
            print(f"[回填][批警告] 批 {bi + 1} 含失败 ticker，已计入 failed_tickers")
        # 填值（仅对成功拉取的 ticker）
        for tk, lut in lut_all.items():
            sub = df[df["Ticker"] == tk]
            for i in sub.index:
                ds = df.at[i, "Date"]
                # 已填跳过
                if (str(df.at[i, "Open"]).strip() not in ("", "nan")
                        and str(df.at[i, "High"]).strip() not in ("", "nan")):
                    continue
                ohlv = lut.get(ds)
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
    print(f"[回填] failed_tickers({len(failed_tickers)}): {','.join(failed_tickers)}")


if __name__ == "__main__":
    main()
