# -*- coding: utf-8 -*-
"""
Quant Factor Backtest —— 阶段 2：因子前瞻收益研究框架（纯研究层，非交易层）。

【定位】
    读取 quant_factor_snapshot.csv（Phase 1 落盘的全候选池因子快照），
    计算每个 (Snapshot, Ticker) 的 Forward Return（5D/10D/20D），
    并产出 Factor × Horizon 的统计摘要 + 五分位 + Market Regime 分层。
    本模块不产生任何交易指令，不反向修改 Scan 选股、Quant_Score、Final_Score、
    Core/Observation 门槛、Review、Portfolio、Dashboard。

【关键纪律】
    1. 只使用 snapshot 中真实产生的因子（绝不历史回填、绝不补造历史因子）。
    2. Look-Ahead 严格禁止：Forward Return 只作为"结果变量"使用，绝不回流进因子。
       因子取值只来自 T 日 snapshot（当时已确定）；未来收益用 T 之后的交易日收盘价。
    3. Selection Bias 严格禁止：回测基于全候选池 snapshot，绝不只测 Core_Dragon /
       Observation / 最终入账推荐。
    4. 无随机性：不 shuffle、不随机切分；同一输入重复运行结果必须逐字节一致。
    5. 样本量门槛：N<30 标 Exploratory Only，N<50 标 Weak Evidence，N>=50 可观察，
       N>=100 才做较正式稳定性比较。任何统计必须输出 N。

【Factor 分类（避免混用）】
    - Raw Factor      : 原始因子（RSI/MACD/MA/ATR/KDJ/量比/Momentum/波动率/ZScore/Beta/RS…）
    - Composite       : Quant_Score（由多因素合成，单独标记）
    - Existing Score  : Fundamental_Score / Event_Score / Technical_Score_25 / Risk_Liquidity_Score

【Forward Return 定义（口径固定）】
    T = Technical_Date（snapshot 行中的"最后完整交易日"）。
    Close[T] = snapshot 行中的 Price 字段（T 日收盘，当时已确定）。
    Forward_Return_ND = Close[T 之后第 N 个交易日] / Close[T] - 1
    对应未来交易日不存在 → None（禁止填 0 / 均值 / 最近日期替代）。
"""

import os
import sys

import numpy as np
import pandas as pd

SNAPSHOT_PATH = "quant_factor_snapshot.csv"
BACKTEST_PATH = "quant_factor_backtest.csv"
SUMMARY_PATH = "quant_factor_summary.csv"

HORIZONS = (5, 10, 20)

# ---- 因子分类（与 Phase 1 snapshot 列名严格一致） ----
RAW_FACTORS = [
    "RSI_14", "Bias_Pct", "MACD_Hist", "MA20", "MA50", "MA20_Slope_5D",
    "ATR_Pct", "KDJ_J", "Volume_Ratio_5D",
    "Momentum_5D_Pct", "Momentum_20D_Pct", "Momentum_60D_Pct",
    "Realized_Volatility_20D_Pct", "Volume_Ratio_20D", "ZScore_20D",
    "Beta_60D_SPY", "Stock_RS_20D_vs_SPY", "Sector_RS_20D_Pct", "VIX",
]
COMPOSITE_FACTORS = ["Quant_Score"]
EXISTING_SCORE_FACTORS = ["Fundamental_Score", "Event_Score", "Technical_Score_25", "Risk_Liquidity_Score"]
ALL_FACTORS = RAW_FACTORS + COMPOSITE_FACTORS + EXISTING_SCORE_FACTORS


def factor_type(factor):
    if factor in COMPOSITE_FACTORS:
        return "Composite"
    if factor in EXISTING_SCORE_FACTORS:
        return "Existing Scan Score"
    return "Raw Factor"


# ============================================================================
# 1. Forward Return 计算（纯函数）
# ============================================================================
def _to_float(v):
    try:
        f = float(v)
        if np.isnan(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def forward_return_nd(price_series, technical_date, close_t, n):
    """计算 T 之后第 n 个交易日的前瞻收益。

    price_series: pd.Series，index 为升序的交易日（tz-naive DatetimeIndex），value 为收盘价。
    technical_date: T（最后完整交易日）。
    close_t: Close[T]（snapshot 的 Price 字段）。
    n: 前瞻交易日数。

    返回 float 或 None（未来交易日不存在 / 价格无效）。
    """
    if close_t is None or close_t <= 0:
        return None
    if price_series is None or price_series.empty:
        return None
    try:
        ts = pd.Timestamp(technical_date).normalize()
    except Exception:
        return None

    # 定位 T 之后第一个交易日
    pos = price_series.index.searchsorted(ts, side="right")
    target = pos + n - 1  # T 之后第 n 个交易日
    if target < 0 or target >= len(price_series):
        return None
    future_close = _to_float(price_series.iloc[target])
    if future_close is None or future_close <= 0:
        return None
    return round((future_close / close_t - 1.0), 6)


def compute_forward_returns(snapshot_df, price_map, horizons=HORIZONS):
    """给 snapshot 增加 Forward_Return_ND / Win_ND 列，返回新 DataFrame（不修改入参）。

    price_map: dict[ticker] -> pd.Series(index=交易日, value=收盘价)，按日期升序。
    """
    df = snapshot_df.copy()
    for n in horizons:
        df[f"Forward_Return_{n}D"] = None
        df[f"Win_{n}D"] = None

    for idx, row in df.iterrows():
        ticker = str(row.get("Ticker", "") or "").strip()
        tech_date = str(row.get("Technical_Date", "") or "").strip()
        close_t = _to_float(row.get("Price"))
        series = price_map.get(ticker) if price_map else None
        for n in horizons:
            fr = forward_return_nd(series, tech_date, close_t, n)
            if fr is None:
                df.at[idx, f"Forward_Return_{n}D"] = None
                df.at[idx, f"Win_{n}D"] = None
            else:
                df.at[idx, f"Forward_Return_{n}D"] = fr
                df.at[idx, f"Win_{n}D"] = 1 if fr > 0 else 0
    return df


# ============================================================================
# 2. 五分位分组（纯函数）
# ============================================================================
def assign_quantile(values, n_bins=5):
    """把一组数值横截面分为 n_bins 档，返回 'Q1'..'Qn' 的 Series（同值安全）。

    - 非空样本不足 n_bins → 全部返回 None（该日/该因子数据不足，不强行分组）。
    - 用 qcut(duplicates='drop') 处理同值，绝不抛错。
    """
    s = pd.Series(values, dtype=float)
    valid = s.dropna()
    out = pd.Series([None] * len(s), index=s.index)
    if len(valid) < n_bins:
        return out
    try:
        bins = pd.qcut(valid, n_bins, labels=[f"Q{i+1}" for i in range(n_bins)], duplicates="drop")
    except Exception:
        return out
    out.loc[bins.index] = bins.astype(str).values
    return out


def compute_quantile_stats(bt_df, factor, horizon, n_bins=5, group_by_date=True):
    """按因子横截面五分位，返回每档的 N / WinRate / Avg / Median。

    group_by_date=True 时：在每个 Snapshot_Date 内做横截面分档（避免跨日分布漂移）。
    """
    ret_col = f"Forward_Return_{horizon}D"
    required = {"Snapshot_Date", "Ticker", factor, ret_col}
    if not required.issubset(bt_df.columns):
        return pd.DataFrame()

    work = bt_df.copy()
    work["_ret"] = pd.to_numeric(work[ret_col], errors="coerce")
    work["_f"] = pd.to_numeric(work[factor], errors="coerce")
    work = work.dropna(subset=["_ret"]).copy()  # 无前瞻收益的样本不进入统计
    if work.empty:
        return pd.DataFrame()

    def _bucket(g):
        q = assign_quantile(g["_f"], n_bins)
        return q

    if group_by_date:
        work["_q"] = work.groupby("Snapshot_Date", group_keys=False).apply(_bucket)
    else:
        work["_q"] = assign_quantile(work["_f"], n_bins)

    rows = []
    valid_q = work[work["_q"].notna()]
    for q in [f"Q{i+1}" for i in range(n_bins)]:
        g = valid_q[valid_q["_q"] == q]
        if g.empty:
            continue
        r = g["_ret"]
        rows.append({
            "Factor": factor,
            "Horizon": f"{horizon}D",
            "Quantile": q,
            "N": int(len(g)),
            "Win_Rate": round(float((r > 0).mean() * 100), 2),
            "Average_Return": round(float(r.mean()), 6),
            "Median_Return": round(float(r.median()), 6),
        })
    return pd.DataFrame(rows)


# ============================================================================
# 3. Factor × Horizon 汇总（纯函数）
# ============================================================================
def compute_factor_summary(bt_df):
    """每个 Factor × Horizon 的整体统计（N / WinRate / Avg / Median / Std / Pos / Neg）。"""
    rows = []
    for factor in ALL_FACTORS:
        if factor not in bt_df.columns:
            continue
        for n in HORIZONS:
            ret_col = f"Forward_Return_{n}D"
            if ret_col not in bt_df.columns:
                continue
            r = pd.to_numeric(bt_df[ret_col], errors="coerce").dropna()
            if r.empty:
                rows.append({
                    "Factor": factor, "Factor_Type": factor_type(factor),
                    "Horizon": f"{n}D", "N": 0, "Valid_Returns": 0,
                    "Win_Rate": None, "Average_Return": None, "Median_Return": None,
                    "Std_Return": None, "Positive_Return_Count": 0, "Negative_Return_Count": 0,
                })
                continue
            pos = int((r > 0).sum())
            neg = int((r <= 0).sum())
            rows.append({
                "Factor": factor, "Factor_Type": factor_type(factor),
                "Horizon": f"{n}D", "N": int(len(r)), "Valid_Returns": int(len(r)),
                "Win_Rate": round(float(pos / len(r) * 100), 2),
                "Average_Return": round(float(r.mean()), 6),
                "Median_Return": round(float(r.median()), 6),
                "Std_Return": round(float(r.std(ddof=1)), 6) if len(r) >= 2 else None,
                "Positive_Return_Count": pos, "Negative_Return_Count": neg,
            })
    return pd.DataFrame(rows)


def compute_correlation(bt_df, factor, horizon):
    """Pearson + Spearman 相关系数（辅助指标，不作为有效性判定唯一依据）。"""
    ret_col = f"Forward_Return_{horizon}D"
    if factor not in bt_df.columns or ret_col not in bt_df.columns:
        return None, None
    work = pd.DataFrame({
        "f": pd.to_numeric(bt_df[factor], errors="coerce"),
        "r": pd.to_numeric(bt_df[ret_col], errors="coerce"),
    }).dropna()
    if len(work) < 3:
        return None, None
    pearson = float(work["f"].corr(work["r"]))
    spearman = float(work["f"].corr(work["r"], method="spearman"))
    return round(pearson, 4), round(spearman, 4)


# ============================================================================
# 4. Market Regime 分层（纯函数）
# ============================================================================
def compute_regime_summary(bt_df):
    """Factor × Horizon × Market_Regime 的 N / WinRate / Avg / Median。"""
    rows = []
    regimes = ["NORMAL", "STRESSED", "PANIC"]
    for factor in ALL_FACTORS:
        if factor not in bt_df.columns:
            continue
        for n in HORIZONS:
            ret_col = f"Forward_Return_{n}D"
            if ret_col not in bt_df.columns:
                continue
            for regime in regimes:
                sub = bt_df[bt_df.get("Market_Regime", pd.Series(dtype=str)).astype(str) == regime]
                r = pd.to_numeric(sub[ret_col], errors="coerce").dropna()
                if r.empty:
                    continue
                rows.append({
                    "Factor": factor, "Horizon": f"{n}D", "Market_Regime": regime,
                    "N": int(len(r)),
                    "Win_Rate": round(float((r > 0).mean() * 100), 2),
                    "Average_Return": round(float(r.mean()), 6),
                    "Median_Return": round(float(r.median()), 6),
                })
    return pd.DataFrame(rows)


# ============================================================================
# 5. 数据成熟度判断
# ============================================================================
def maturity_status(price_map, snapshot_df, horizon):
    """判断给定 horizon 是否已有足够后续交易日的数据（返回成熟样本数）。"""
    if price_map is None or snapshot_df.empty:
        return 0
    mature = 0
    for _, row in snapshot_df.iterrows():
        ticker = str(row.get("Ticker", "") or "").strip()
        tech_date = str(row.get("Technical_Date", "") or "").strip()
        close_t = _to_float(row.get("Price"))
        series = price_map.get(ticker)
        if forward_return_nd(series, tech_date, close_t, horizon) is not None:
            mature += 1
    return mature


def sample_size_label(n):
    if n is None or n < 30:
        return "Exploratory Only"
    if n < 50:
        return "Weak Evidence"
    if n < 100:
        return "Observable Trend"
    return "Formal Comparison OK"


# ============================================================================
# 6. 价格加载器（可选，批量下载，绝不逐 stock×horizon 重复请求）
# ============================================================================
def load_price_history(tickers, start, end, auto_adjust=True):
    """一次性批量下载 tickers 的日线，返回 {ticker: Series(index=交易日, value=Close)}。

    仅在 snapshot 非空且需要计算 Forward Return 时调用；每次运行最多一次批量请求。
    """
    import yfinance as yf

    tickers = list(dict.fromkeys([str(t).upper() for t in tickers if str(t).strip()]))
    if not tickers:
        return {}
    try:
        data = yf.download(tickers, start=start, end=end, progress=False,
                           auto_adjust=auto_adjust, threads=True, group_by="ticker")
    except Exception:
        return {}

    price_map = {}
    for t in tickers:
        try:
            if len(tickers) == 1:
                df = data
            else:
                df = data[t]
            if df is None or df.empty:
                continue
            close = pd.to_numeric(df["Close"], errors="coerce").dropna()
            idx = pd.to_datetime(close.index, errors="coerce")
            try:
                idx = idx.tz_localize(None)
            except Exception:
                pass
            close.index = idx.normalize()
            close = close.sort_index()
            price_map[t] = close
        except Exception:
            continue
    return price_map


# ============================================================================
# 7. 主入口
# ============================================================================
def run_backtest(snapshot_path=SNAPSHOT_PATH, price_map=None,
                 backtest_path=BACKTEST_PATH, summary_path=SUMMARY_PATH):
    """读 snapshot → 计算 forward return → 写 backtest.csv 与 summary.csv。返回状态 dict。"""
    result = {
        "snapshot_rows": 0,
        "status": "NOT_ENOUGH_DATA",
        "backtest_rows": 0,
        "summary_rows": 0,
        "maturity": {},
    }

    if not os.path.exists(snapshot_path):
        result["reason"] = f"snapshot 不存在：{snapshot_path}"
        _write_empty(backtest_path, summary_path)
        return result

    try:
        snap = pd.read_csv(snapshot_path, dtype=str, keep_default_na=False)
    except Exception as e:
        result["reason"] = f"snapshot 读取失败：{type(e).__name__}: {e}"
        _write_empty(backtest_path, summary_path)
        return result

    if snap.empty:
        result["reason"] = "snapshot 为空（尚无真实因子数据，绝不做历史回填）"
        _write_empty(backtest_path, summary_path)
        return result

    result["snapshot_rows"] = int(len(snap))

    # 数据成熟度：判断每个 horizon 是否有足够后续交易日
    for n in HORIZONS:
        result["maturity"][f"{n}D"] = maturity_status(price_map, snap, n)

    # 无价格数据 → 无法计算 forward return，写空表并报告缺口
    if not price_map:
        result["reason"] = "价格数据不足（无 price_map），先建立框架并报告缺口，不擅自抓取"
        _write_empty(backtest_path, summary_path)
        return result

    bt = compute_forward_returns(snap, price_map)
    result["backtest_rows"] = int(len(bt))
    bt.to_csv(backtest_path, index=False, encoding="utf-8")

    summary = compute_factor_summary(bt)
    result["summary_rows"] = int(len(summary))
    summary.to_csv(summary_path, index=False, encoding="utf-8")

    result["status"] = "OK"
    return result


def _write_empty(backtest_path, summary_path):
    for p in (backtest_path, summary_path):
        if p:
            with open(p, "w", encoding="utf-8") as f:
                f.write("")
