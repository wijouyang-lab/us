# -*- coding: utf-8 -*-
"""
Persistent Price History Layer —— 阶段 2B：为 Factor Snapshot 提供 Forward Return 的真实历史价格。

【定位】
    独立研究层，为 quant_factor_backtest.py 提供 T+5 / T+10 / T+20 前瞻收益所需的
    真实历史收盘价。绝不参与、也绝不修改 Scan 选股 / Quant_Score / Final_Score /
    Core-Observation gate / Stop Loss / Review / Portfolio / Dashboard / Options。

【T 日价格口径（与 Phase 1 严格一致，勿擅自更改）】
    - Phase 1 因子计算使用 get_kline_data()，其 yfinance 参数为 auto_adjust=False（未复权），
      并经 _filter_completed_daily_bars() 剔除未完成 bar，因此 close[-1] 一定是
      "最后完整常规交易日"的未复权收盘价。
    - Snapshot 行的 Technical_Date = 该最后完整交易日；Price = 该日 Close。
    - 本模块的 Price History 同样使用 auto_adjust=False + 完整交易日过滤，
      保证 Close[T] 与 Snapshot 的 Price 同源同口径。

【禁止】
    - 绝不根据价格历史反向生成/回填历史 Factor Snapshot。
    - 绝不使用 Review / Exit_Price / Stop_Loss / AI 结果补价格洞。
    - 未来交易日不存在 → 缺价格（None），绝不填 0 / 插值 / 用最近交易日替代。

【数据文件】
    quant_factor_price_history.csv，字段：Date, Ticker, Open, High, Low, Close, Volume
    （外加 schema_version 跟踪列）。唯一键：Date | Ticker（幂等 upsert，历史记录不被覆盖）。
    - Close 仍是前瞻收益（Forward Return）的唯一口径，列名与含义不变（兼容 Phase 2 回测）。
    - Open/High/Low/Volume 为 OHLCV 补采，供未来（开盘跳空、真实止损/止盈、流动性建模）使用，
      当前回测/验证/候选/Shadow/Walk-Forward/治理 均不消费这四列，加列不影响任何既有链路。
"""

import os
import sys
from datetime import datetime, time as dtime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

US_TZ = ZoneInfo("America/New_York")

PRICE_HISTORY_PATH = "quant_factor_price_history.csv"
# OHLCV 补采（STEP）：在原有 Date, Ticker, Close 基础上扩到 Open/High/Low/Close/Volume。
# Close 列名与位置含义不变（仍紧邻 Ticker 之后、Volume 之前），兼容 Phase 2 回测的 price_map。
PRICE_HISTORY_COLUMNS = ["Date", "Ticker", "Open", "High", "Low", "Close", "Volume", "schema_version"]

# 输出 schema 版本（STEP 3-A）：写入 quant_factor_price_history.csv 的 schema_version 列。
# 命名规则：phase<阶段>.v<主版本>，与 Phase 1–7 完全一致；字段结构变更时递增主版本号。
# 本次新增 Open/High/Low/Volume 四列 → 主版本号 v1 → v2。
SCHEMA_VERSION = "phase2b.v2"

SNAPSHOT_PATH = "quant_factor_snapshot.csv"


# ============================================================================
# 交易日口径（与 scan.py 的 _last_completed_regular_date_us 完全一致）
# ============================================================================
def last_completed_regular_date_us(asof=None):
    """返回最后完整美股常规交易日日期（美东口径）。

    now.time() < 16:00 → 昨天；否则 → 今天。
    """
    now = asof or datetime.now(US_TZ)
    if now.time() < dtime(16, 0):
        return (now - timedelta(days=1)).date()
    return now.date()


def _normalize_us_date_index(df):
    """把 yfinance 日线 index 统一为美东时区的 DatetimeIndex（tz-naive）。"""
    out = df.copy()
    idx = pd.to_datetime(out.index, errors="coerce")
    valid = ~idx.isna()
    out = out.loc[valid].copy()
    idx = pd.DatetimeIndex(idx[valid])
    if idx.tz is None:
        idx_us = idx.tz_localize("UTC").tz_convert(US_TZ)
    else:
        idx_us = idx.tz_convert(US_TZ)
    out.index = idx_us
    out.index.name = "Date"
    return out


def filter_completed_daily_bars(df, cutoff_date):
    """剔除 cutoff_date 之后的（未完成）日线 bar。纯函数。"""
    if df is None or df.empty:
        return pd.DataFrame()
    out = _normalize_us_date_index(df)
    cutoff = pd.Timestamp(cutoff_date).normalize()
    # 统一用 tz-naive 的 date 比较（与 scan.py 的 index.date <= cutoff 口径一致）
    keep = out.index.tz_localize(None).normalize() <= cutoff
    return out.loc[keep].copy()


# ============================================================================
# Snapshot Universe（全候选池历史 ticker）
# ============================================================================
def get_snapshot_tickers(snapshot_df):
    """返回 snapshot 历史上出现过的所有 Ticker（去重、大写、排序）。"""
    if snapshot_df is None or snapshot_df.empty:
        return []
    if "Ticker" not in snapshot_df.columns:
        return []
    tickers = [str(t).strip().upper() for t in snapshot_df["Ticker"].tolist() if str(t).strip()]
    return sorted(dict.fromkeys(tickers))


# ============================================================================
# 批量价格下载（单次批量，绝不逐 ticker 循环请求）
# ============================================================================
def fetch_batch_prices(tickers, start, end, auto_adjust=False, cutoff_date=None):
    """一次性批量下载 tickers 的日线 OHLCV，返回长表 DataFrame[Date, Ticker, Open, High, Low, Close, Volume, schema_version]。

    - 单次 yf.download(tickers, ...)，绝不为每个 ticker 单独请求。
    - auto_adjust=False，与 Phase 1 因子口径一致。
    - cutoff_date 默认为最后完整交易日（剔除未完成 bar）。
    - Close 仍为必填（前瞻收益口径不变）；Open/High/Low/Volume 缺失则该行留空（不强行补 0 / 不阻断）。
    """
    import yfinance as yf

    OHLCV = ["Open", "High", "Low", "Close", "Volume"]
    tickers = list(dict.fromkeys([str(t).upper() for t in tickers if str(t).strip()]))
    if not tickers:
        return pd.DataFrame(columns=PRICE_HISTORY_COLUMNS)
    cutoff = cutoff_date or last_completed_regular_date_us()
    try:
        data = yf.download(tickers, start=start, end=end, progress=False,
                           auto_adjust=auto_adjust, threads=True, group_by="ticker")
    except Exception:
        return pd.DataFrame(columns=PRICE_HISTORY_COLUMNS)

    rows = []
    for t in tickers:
        try:
            if len(tickers) == 1:
                df = data
            else:
                df = data[t] if t in data.columns.get_level_values(0) else None
            if df is None or df.empty:
                continue
            if "Close" not in df.columns:
                continue
            # 仅取存在的 OHLCV 列；缺失列不强行补（与"绝不填 0 / 插值"铁律一致）
            present = [c for c in OHLCV if c in df.columns]
            if "Close" not in present:
                continue
            sub = pd.DataFrame({c: pd.to_numeric(df[c], errors="coerce") for c in present})
            sub = filter_completed_daily_bars(sub, cutoff)
            sub = sub.dropna(subset=["Close"])  # Close 必填
            for d, row in sub.iterrows():
                rec = {
                    "Date": d.normalize().strftime("%Y-%m-%d"),
                    "Ticker": t,
                    "Close": round(float(row["Close"]), 6),
                    "schema_version": SCHEMA_VERSION,
                }
                for c in ("Open", "High", "Low", "Volume"):
                    v = row.get(c)
                    if v is None or pd.isna(v):
                        rec[c] = ""
                    elif c == "Volume":
                        rec[c] = int(round(float(v)))
                    else:
                        rec[c] = round(float(v), 6)
                rows.append(rec)
        except Exception:
            continue
    if not rows:
        return pd.DataFrame(columns=PRICE_HISTORY_COLUMNS)
    out = pd.DataFrame(rows, columns=PRICE_HISTORY_COLUMNS)
    return out.drop_duplicates(subset=["Date", "Ticker"]).sort_values(["Ticker", "Date"]).reset_index(drop=True)


# ============================================================================
# 幂等 upsert（历史不被覆盖）
# ============================================================================
def load_price_history(path=PRICE_HISTORY_PATH):
    if not os.path.exists(path):
        return pd.DataFrame(columns=PRICE_HISTORY_COLUMNS)
    try:
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        for c in PRICE_HISTORY_COLUMNS:
            if c not in df.columns:
                df[c] = ""
        return df[PRICE_HISTORY_COLUMNS]
    except Exception:
        return pd.DataFrame(columns=PRICE_HISTORY_COLUMNS)


def upsert_price_history(existing_df, new_df):
    """按 Date|Ticker 幂等合并：新记录追加，已有历史记录保持原值不被覆盖。纯函数。"""
    existing = existing_df if existing_df is not None else pd.DataFrame(columns=PRICE_HISTORY_COLUMNS)
    incoming = new_df if new_df is not None else pd.DataFrame(columns=PRICE_HISTORY_COLUMNS)
    if existing.empty and incoming.empty:
        return pd.DataFrame(columns=PRICE_HISTORY_COLUMNS)
    if existing.empty:
        return incoming.drop_duplicates(subset=["Date", "Ticker"]).sort_values(["Ticker", "Date"]).reset_index(drop=True)

    existing = existing.copy()
    incoming = incoming.copy()
    existing["_key"] = existing["Date"].astype(str) + "|" + existing["Ticker"].astype(str)
    incoming["_key"] = incoming["Date"].astype(str) + "|" + incoming["Ticker"].astype(str)

    # 只保留"历史中不存在"的新 key，绝不覆盖历史
    new_only = incoming[~incoming["_key"].isin(set(existing["_key"]))].copy()
    if new_only.empty:
        merged = existing.drop(columns=["_key"])
        return merged.sort_values(["Ticker", "Date"]).reset_index(drop=True)

    merged = pd.concat([existing, new_only], ignore_index=True)
    merged = merged.drop(columns=["_key"])
    merged = merged.drop_duplicates(subset=["Date", "Ticker"], keep="first")
    merged = merged.sort_values(["Ticker", "Date"]).reset_index(drop=True)
    return merged


def price_map_from_history(price_history_df):
    """从长表构建 {ticker: Series(index=交易日, value=Close)}，供 backtest 使用。"""
    pm = {}
    if price_history_df is None or price_history_df.empty:
        return pm
    for t, g in price_history_df.groupby("Ticker"):
        s = pd.Series(
            pd.to_numeric(g["Close"], errors="coerce").values,
            index=pd.to_datetime(g["Date"], errors="coerce"),
        )
        s = s.dropna().sort_index()
        if not s.empty:
            pm[str(t)] = s
    return pm


# ============================================================================
# 主入口：更新价格历史
# ============================================================================
def update_price_history(snapshot_path=SNAPSHOT_PATH, price_history_path=PRICE_HISTORY_PATH,
                         start=None, end=None, fetch_func=None):
    """读 snapshot → 找历史所有 ticker → 批量下载 → 幂等 upsert → 原子写。返回状态 dict。

    fetch_func 可注入（测试用），默认 fetch_batch_prices。
    """
    result = {
        "snapshot_rows": 0,
        "unique_tickers": 0,
        "new_rows": 0,
        "total_rows": 0,
        "status": "NO_SNAPSHOT",
    }

    if not os.path.exists(snapshot_path):
        result["reason"] = f"snapshot 不存在：{snapshot_path}"
        return result
    try:
        snap = pd.read_csv(snapshot_path, dtype=str, keep_default_na=False)
    except Exception as e:
        result["reason"] = f"snapshot 读取失败：{type(e).__name__}: {e}"
        return result

    if snap.empty:
        result["status"] = "EMPTY_SNAPSHOT"
        result["reason"] = "snapshot 为空（Price History 保持为空，Backtest 将 NOT_ENOUGH_DATA）"
        return result

    result["snapshot_rows"] = int(len(snap))
    tickers = get_snapshot_tickers(snap)
    result["unique_tickers"] = len(tickers)
    if not tickers:
        result["status"] = "NO_TICKERS"
        return result

    # 下载范围：覆盖 snapshot 最早 Technical_Date（往前留缓冲）到今天
    if start is None:
        min_date = pd.to_datetime(snap.get("Technical_Date"), errors="coerce").min()
        if pd.isna(min_date):
            min_date = pd.Timestamp.today()
        start = (min_date - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
    if end is None:
        end = (datetime.now(US_TZ) + timedelta(days=1)).strftime("%Y-%m-%d")

    fn = fetch_func or fetch_batch_prices
    new_df = fn(tickers, start, end)

    existing = load_price_history(price_history_path)
    merged = upsert_price_history(existing, new_df)
    result["new_rows"] = int(len(merged) - len(existing))
    result["total_rows"] = int(len(merged))

    # 原子写
    tmp = price_history_path + ".tmp"
    merged.to_csv(tmp, index=False, encoding="utf-8")
    os.replace(tmp, price_history_path)

    result["status"] = "OK"
    return result


def main(argv=None):
    r = update_price_history()
    print("[Price History]", r)
    return 0 if r["status"] in ("OK", "NO_SNAPSHOT", "EMPTY_SNAPSHOT", "NO_TICKERS") else 1


if __name__ == "__main__":
    sys.exit(main())
