# -*- coding: utf-8 -*-
"""
Quant Factor Lab —— 阶段 1：标准量化因子库 + 每日候选池因子快照。

【定位】
    本模块是"研究/数据层"，只负责把 Scan 已经拿到手的数据计算成可回测的因子，
    并落盘为每日全候选池快照。它绝不参与 Scan 选股、Quant_Score、Final_Score、
    Core/Observation 门槛、Regime Gate、Stop Loss 或 AI 选择。

【关键约定】
    - 本模块不 import yfinance，不做任何网络请求（SPY 数据由 scan.py 传入）。
    - 所有因子函数都是纯函数：输入 pandas Series/DataFrame，输出 float 或 None。
    - 数据不足 / 除零 / NaN → 返回 None（fail-safe，绝不填 0、均值或猜测值）。
    - Look-Ahead 纪律：因子只读取传入序列的历史窗口（当前 bar 及之前），
      绝不读取 Exit_Price / PnL / Review 里程碑 / AI 推荐结果等未来数据。

============================================================================
因子定义（口径固定，禁止后续悄悄改动；改动必须更新本表并升级 snapshot 版本）
============================================================================
A. Momentum_5D_Pct
    定义:  (close[-1] / close[-6] - 1) * 100
    窗口:  当前收盘 vs 5 个交易日前收盘（共需 >= 6 根 bar）
    口径:  不 annualize；包含当前 bar（close[-1] 即最新完整交易日）

B. Momentum_20D_Pct
    定义:  (close[-1] / close[-21] - 1) * 100
    窗口:  当前收盘 vs 20 个交易日前收盘（共需 >= 21 根 bar）

C. Momentum_60D_Pct
    定义:  (close[-1] / close[-61] - 1) * 100
    窗口:  当前收盘 vs 60 个交易日前收盘（共需 >= 61 根 bar）

D. Realized_Volatility_20D_Pct
    定义:  std(daily_return[-20:], ddof=1) * sqrt(252) * 100
           daily_return[t] = close[t]/close[t-1] - 1
    窗口:  最近 20 个有效日收益率（共需 >= 21 根 bar）
    口径:  annualize（sqrt(252)）；结果为百分比年化波动率

E. Volume_Ratio_20D
    定义:  volume[-1] / mean(volume[-21:-1])
    窗口:  当前完整交易日成交量 / 前 20 个交易日平均成交量（平均值不含当前 bar）
    口径:  需要 >= 21 根 bar；mean 为空或 0 → None

F. ZScore_20D
    定义:  (close[-1] - mean(close[-21:-1])) / std(close[-21:-1], ddof=1)
    窗口:  当前收盘 相对 前 20 个交易日收盘的标准化位置（均值/标准差不含当前 bar）
    口径:  需要 >= 21 根 bar；std == 0 → None

G. Beta_60D_SPY
    定义:  Cov(stock_return, spy_return) / Var(spy_return)
    窗口:  最近 60 个有效"重叠"日收益率（按共同交易日对齐）
    口径:  spy_return 方差为 0 / NaN → None（不除零）；重叠样本 < 60 → None

H. Stock_RS_20D_vs_SPY
    定义:  (stock_close[-1]/stock_close[-21]-1)*100 - (spy_close[-1]/spy_close[-21]-1)*100
    窗口:  个股 20D 收益 减去 SPY 20D 收益（共需 >= 21 根 bar）
    口径:  结果为百分点差；SPY 缺失 → None
============================================================================
"""

import os

import numpy as np
import pandas as pd


# 因子快照列顺序（固定，供后续 Backtest 直接按列名读取）
SNAPSHOT_COLUMNS = [
    "Scan_Date", "Technical_Date", "Ticker", "Name", "Sector",
    "Price",
    "RSI_14", "Bias_Pct", "MACD_Hist", "MA20", "MA50", "MA20_Slope_5D",
    "ATR_Pct", "KDJ_J", "Volume_Ratio_5D",
    "Momentum_5D_Pct", "Momentum_20D_Pct", "Momentum_60D_Pct",
    "Realized_Volatility_20D_Pct", "Volume_Ratio_20D", "ZScore_20D",
    "Beta_60D_SPY", "Stock_RS_20D_vs_SPY",
    "Sector_RS_20D_Pct", "VIX", "Market_Regime",
    "Fundamental_Score", "Event_Score", "Technical_Score_25",
    "Risk_Liquidity_Score", "Quant_Score",
    "技术确认数", "Gate_Status",
    "schema_version",
]

# 幂等唯一键：Scan_Date | Ticker（同一扫描日同一标的只保留一行）
KEY_COLUMNS = ("Scan_Date", "Ticker")

# 输出 schema 版本（STEP 3-A）：写入 quant_factor_snapshot.csv 的 schema_version 列。
# 命名规则：phase<阶段>.v<主版本>，与 Phase 2–7 完全一致；字段结构变更时递增主版本号。
# 用途：下游 Dashboard / 各 Phase 读取时先校验版本，避免字段变化导致静默错误。
SCHEMA_VERSION = "phase1.v1"


# ============================================================================
# 纯因子计算函数
# ============================================================================
def _clean_series(series):
    """转成 float、去 NaN，返回升序 Series（不改变传入对象）。"""
    if series is None:
        return pd.Series(dtype=float)
    if isinstance(series, pd.Series):
        s = series.copy()
    else:
        s = pd.Series(series)
    s = pd.to_numeric(s, errors="coerce").dropna()
    return s.reset_index(drop=True)


def _daily_index(series):
    """把带时区/带时间的 DatetimeIndex 归一化为 tz-naive 的日期，供不同来源序列对齐。"""
    s = series.dropna()
    if isinstance(s.index, pd.DatetimeIndex):
        idx = s.index
        if getattr(idx, "tz", None) is not None:
            idx = idx.tz_localize(None)
        s = s.copy()
        s.index = idx.normalize()
    return s


def momentum_pct(close, n):
    """(close[-1] / close[-(n+1)] - 1) * 100；数据不足返回 None。"""
    c = _clean_series(close)
    if len(c) < n + 1:
        return None
    base = float(c.iloc[-1 - n])
    if base <= 0:
        return None
    return round((float(c.iloc[-1]) / base - 1.0) * 100.0, 4)


def realized_volatility_20d_pct(close):
    """最近 20 个日收益率 std(ddof=1) * sqrt(252) * 100；不足 21 根返回 None。"""
    c = _clean_series(close)
    if len(c) < 21:
        return None
    ret = c.pct_change().dropna()
    if len(ret) < 20:
        return None
    ret = ret.iloc[-20:]
    std = float(ret.std(ddof=1))
    if np.isnan(std):
        return None
    return round(std * np.sqrt(252.0) * 100.0, 4)


def volume_ratio_20d(volume):
    """volume[-1] / mean(volume[-21:-1])；不足 21 根或均值为 0 → None。"""
    v = _clean_series(volume)
    if len(v) < 21:
        return None
    prev_mean = float(v.iloc[-21:-1].mean())
    if prev_mean <= 0 or np.isnan(prev_mean):
        return None
    cur = float(v.iloc[-1])
    return round(cur / prev_mean, 4)


def zscore_20d(close):
    """(close[-1] - mean(前20)) / std(前20, ddof=1)；std 为 0 → None。"""
    c = _clean_series(close)
    if len(c) < 21:
        return None
    prev = c.iloc[-21:-1]
    std = float(prev.std(ddof=1))
    if std == 0 or np.isnan(std):
        return None
    return round((float(c.iloc[-1]) - float(prev.mean())) / std, 4)


def beta_60d(stock_close, spy_close):
    """Cov(stock_ret, spy_ret) / Var(spy_ret)，最近 60 个重叠日收益率；除零/样本不足 → None。"""
    s = _daily_index(_clean_series(stock_close)) if stock_close is not None else pd.Series(dtype=float)
    p = _daily_index(_clean_series(spy_close)) if spy_close is not None else pd.Series(dtype=float)
    if len(s) < 61 or len(p) < 61:
        return None
    sr = s.pct_change().dropna()
    pr = p.pct_change().dropna()
    common = sr.index.intersection(pr.index)
    if len(common) < 60:
        return None
    sr = sr.loc[common].iloc[-60:]
    pr = pr.loc[common].iloc[-60:]
    if len(sr) < 60 or len(pr) < 60:
        return None
    var = float(pr.var(ddof=1))
    if var == 0 or np.isnan(var):
        return None
    beta = float(sr.cov(pr) / var)
    return round(beta, 4)


def stock_rs_20d_vs_spy(stock_close, spy_close):
    """个股 20D 收益(%) - SPY 20D 收益(%)；数据不足/SPY 缺失 → None。"""
    s = _clean_series(stock_close)
    p = _clean_series(spy_close)
    if len(s) < 21 or len(p) < 21:
        return None
    s_ret = float(s.iloc[-1]) / float(s.iloc[-21]) - 1.0
    p_ret = float(p.iloc[-1]) / float(p.iloc[-21]) - 1.0
    return round((s_ret - p_ret) * 100.0, 4)


def calculate_extended_quant_factors(df, spy_close=None):
    """从个股 OHLCV DataFrame 计算 8 个扩展因子，返回 dict（值为 float 或 None）。

    df 需含 Close / Volume 列；spy_close 为 SPY 收盘 Series（可空，空时 Beta/RS 为 None）。
    """
    if df is None or df.empty:
        close = pd.Series(dtype=float)
        volume = pd.Series(dtype=float)
    else:
        close = df["Close"] if "Close" in df.columns else pd.Series(dtype=float)
        volume = df["Volume"] if "Volume" in df.columns else pd.Series(dtype=float)
    return {
        "Momentum_5D_Pct": momentum_pct(close, 5),
        "Momentum_20D_Pct": momentum_pct(close, 20),
        "Momentum_60D_Pct": momentum_pct(close, 60),
        "Realized_Volatility_20D_Pct": realized_volatility_20d_pct(close),
        "Volume_Ratio_20D": volume_ratio_20d(volume),
        "ZScore_20D": zscore_20d(close),
        "Beta_60D_SPY": beta_60d(close, spy_close),
        "Stock_RS_20D_vs_SPY": stock_rs_20d_vs_spy(close, spy_close),
    }


# ============================================================================
# Snapshot 写入（幂等 upsert + 原子写）
# ============================================================================
def _fmt(value, nd=None):
    """数值格式化为字符串；None/NaN → 空串。"""
    if value is None:
        return ""
    try:
        f = float(value)
        if np.isnan(f):
            return ""
    except (TypeError, ValueError):
        return str(value)
    if nd is None:
        return str(value)
    return f"{f:.{nd}f}"


def build_snapshot_rows(pool, scan_date):
    """从候选池 item 列表提取 snapshot 行（纯函数，不写盘）。"""
    rows = []
    for item in pool or []:
        rows.append({
            "schema_version": SCHEMA_VERSION,
            "Scan_Date": str(scan_date),
            "Technical_Date": str(item.get("Technical_Date", "") or ""),
            "Ticker": str(item.get("Ticker", "") or ""),
            "Name": str(item.get("Name", "") or ""),
            "Sector": str(item.get("Sector", "") or ""),
            "Price": _fmt(item.get("Price"), 2),
            "RSI_14": _fmt(item.get("RSI"), 1),
            "Bias_Pct": _fmt(item.get("乖离率(%)"), 2),
            "MACD_Hist": _fmt(item.get("MACD_HIST_LAST"), 4),
            "MA20": _fmt(item.get("MA20"), 2),
            "MA50": _fmt(item.get("MA50"), 2),
            "MA20_Slope_5D": _fmt(item.get("MA20_Slope_Pct_5D"), 3),
            "ATR_Pct": _fmt(item.get("ATR_Pct"), 2),
            "KDJ_J": _fmt(item.get("KDJ_J"), 2),
            "Volume_Ratio_5D": _fmt(item.get("量比"), 4),
            "Momentum_5D_Pct": _fmt(item.get("Momentum_5D_Pct"), 4),
            "Momentum_20D_Pct": _fmt(item.get("Momentum_20D_Pct"), 4),
            "Momentum_60D_Pct": _fmt(item.get("Momentum_60D_Pct"), 4),
            "Realized_Volatility_20D_Pct": _fmt(item.get("Realized_Volatility_20D_Pct"), 4),
            "Volume_Ratio_20D": _fmt(item.get("Volume_Ratio_20D"), 4),
            "ZScore_20D": _fmt(item.get("ZScore_20D"), 4),
            "Beta_60D_SPY": _fmt(item.get("Beta_60D_SPY"), 4),
            "Stock_RS_20D_vs_SPY": _fmt(item.get("Stock_RS_20D_vs_SPY"), 4),
            "Sector_RS_20D_Pct": _fmt(item.get("Sector_RS_20D_Pct"), 2),
            "VIX": _fmt(item.get("VIX"), 2),
            "Market_Regime": str(item.get("Market_Regime", "") or ""),
            "Fundamental_Score": _fmt(item.get("Fundamental_Score"), 1),
            "Event_Score": _fmt(item.get("Event_Score"), 1),
            "Technical_Score_25": _fmt(item.get("Technical_Score_25"), 1),
            "Risk_Liquidity_Score": _fmt(item.get("Risk_Liquidity_Score"), 1),
            "Quant_Score": _fmt(item.get("Quant_Score"), 1),
            "技术确认数": _fmt(item.get("技术确认数"), 0),
            "Gate_Status": str(item.get("Gate_Status", "") or ""),
        })
    return rows


# ============================================================================
# 契约告警（纯函数 · 只读 · 零副作用）
# ============================================================================
def _norm_date(v):
    """把 str / date / datetime 统一成 datetime.date；无法解析返回 None。"""
    if v is None:
        return None
    try:
        ts = pd.Timestamp(v)
        if pd.isna(ts):
            return None
        return ts.date()
    except Exception:
        return None


def check_technical_date_contract(technical_date, cutoff_date, trading_dates=None):
    """比对 snapshot 的 Technical_Date 与「理论最后完成交易日」，返回只读诊断。

    【为什么要有这个函数】
    设计契约（quant_factor_price.py:10-16）明确写着：
        Technical_Date = 最后完整常规交易日；Price = 该日 Close。
    2026-10-07 首份真实数据中，Technical_Date=2026-10-05，而理论值应为 2026-10-06
    （price history 同期已具备 10-06），即契约未被兑现。为把这种隐性偏差变成
    **每日可见的显性信号**，才有本函数。

    【严格只读】
        · 不修改 Technical_Date 的值
        · 不修改数据源 / 调用方式
        · 不阻断 snapshot 生成
        · 无任何文件写入、无网络请求

    参数
    ----
    technical_date : snapshot 实际写入的 Technical_Date
    cutoff_date    : 理论「最后完整常规交易日」（调用方按美东时点计算）
    trading_dates  : 可选，已知交易日列表（来自 Phase 2B price history）。
                     用于把期望日落在真实交易日上，并精确统计相差【交易日】数。

    返回 dict
    ---------
    status           : OK / STALE / AHEAD / NO_REFERENCE / NO_DATA
    technical_date   : 实际 T
    expected_date    : 理论 T
    gap_trading_days : 相差交易日数（无 trading_dates 时退化为自然日差）
    message          : 说明；STALE 时即为 warning 正文
    """
    t = _norm_date(technical_date)
    c = _norm_date(cutoff_date)
    out = {
        "status": "NO_DATA",
        "technical_date": str(t) if t else None,
        "expected_date": str(c) if c else None,
        "gap_trading_days": None,
        "message": "",
    }

    if t is None or c is None:
        out["status"] = "NO_DATA" if t is None else "NO_REFERENCE"
        out["message"] = (
            "无法完成契约比对：technical_date 缺失" if t is None
            else "无法完成契约比对：cutoff_date 缺失（理论最后完成交易日未知）"
        )
        return out

    # 已知交易日（升序、去重），用于精确定位期望日与相差交易日数
    known = []
    if trading_dates:
        for d in trading_dates:
            nd = _norm_date(d)
            if nd is not None:
                known.append(nd)
        known = sorted(set(known))

    expected = c
    if known:
        le = [d for d in known if d <= c]
        if le:
            expected = max(le)

    out["expected_date"] = str(expected)

    if t > expected:
        # 实际比日历更"新"：通常是 price history 尚未更新到该日，属正常
        out["status"] = "AHEAD"
        out["message"] = (
            f"Technical_Date={t} 晚于已知交易日日历末端 {expected}"
            f"（price history 尚未更新到该日，属正常）"
        )
        return out

    if t == expected:
        out["status"] = "OK"
        out["gap_trading_days"] = 0
        out["message"] = f"Technical_Date={t} 与理论最后完成交易日一致，契约成立"
        return out

    # t < expected → 滞后
    if known:
        gap = len([d for d in known if t < d <= expected])
    else:
        gap = (expected - t).days
    out["status"] = "STALE"
    out["gap_trading_days"] = gap
    out["message"] = (
        f"[Quant Factor Lab][契约告警] Technical_Date={t} 早于理论最后完成交易日 "
        f"{expected}，相差 {gap} 个交易日。"
        f"设计契约要求 Technical_Date = 最后完整常规交易日（见 quant_factor_price.py:10-16），"
        f"本次未兑现。可能原因：get_kline_data() 使用单只 period=\"6mo\" 下载，"
        f"与 fetch_batch_prices() 的批量 start/end 下载存在数据新鲜度差异；"
        f"也可能是该时点行情源尚未更新。建议：持续观测，先不改数据源，"
        f"累积数日后判定是否为系统性滞后。本次不修改 Technical_Date、不阻断落盘。"
    )
    return out


def write_factor_snapshot(pool, path, scan_date):
    """幂等 upsert 写因子快照，返回最终行数。

    - 唯一键 = Scan_Date | Ticker；
    - 本次运行结果覆盖同 key 的旧行，其余历史行保持不变；
    - 原子写 temp 文件后 replace，绝不重复 append duplicate。
    """
    new_rows = build_snapshot_rows(pool, scan_date)
    existing = []
    if os.path.exists(path):
        try:
            existing = pd.read_csv(path, dtype=str, keep_default_na=False).to_dict("records")
        except Exception:
            existing = []

    key_map = {}
    for r in existing:
        key = f"{r.get('Scan_Date', '')}|{r.get('Ticker', '')}"
        key_map[key] = r
    for r in new_rows:
        key = f"{r.get('Scan_Date', '')}|{r.get('Ticker', '')}"
        key_map[key] = r

    merged = [key_map[k] for k in sorted(key_map.keys())]
    df_out = pd.DataFrame(merged, columns=SNAPSHOT_COLUMNS)
    df_out = df_out.fillna("")

    tmp_path = path + ".tmp"
    df_out.to_csv(tmp_path, index=False, encoding="utf-8")
    os.replace(tmp_path, path)
    return len(merged)
