# -*- coding: utf-8 -*-
"""
美股期权推荐引擎
- 只对 Scan 的 Core_Dragon 生成期权建议
- 使用 yfinance 公开期权链，优先 45-90 DTE
- 优先 Call Debit Spread；若无法构建价差则退化为 Long Call
- 同时记录 Delta、IV、Call Wall、Put Wall、Earnings Date
- 不伪造不存在的期权报价；链/报价不足则明确返回 None
"""

import csv
import datetime as dt
import math
import os
import tempfile
from typing import Any, Dict, Optional

import pandas as pd
import yfinance as yf

OPTION_FILE = "option_strategies.csv"
MIN_DTE = 45
MAX_DTE = 90
TARGET_DTE = 60
RISK_FREE = 0.04


def _sf(v, default=None):
    try:
        if v is None or (isinstance(v, str) and not v.strip()):
            return default
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _norm_date(v):
    try:
        return pd.Timestamp(v).date()
    except Exception:
        return None


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _call_delta(spot: float, strike: float, dte: int, iv: float, rate: float = RISK_FREE) -> Optional[float]:
    if min(spot, strike, dte, iv) <= 0:
        return None
    t = dte / 365.0
    sigma = max(0.0001, iv)
    d1 = (math.log(spot / strike) + (rate + 0.5 * sigma * sigma) * t) / (sigma * math.sqrt(t))
    return _normal_cdf(d1)


def _clean_chain(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    for col in ["strike", "lastPrice", "bid", "ask", "volume", "openInterest", "impliedVolatility"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
        else:
            out[col] = float("nan")
    out = out[out["strike"].notna()].copy()
    return out


def _best_price(row, side: str) -> Optional[float]:
    if side == "buy":
        for c in ("ask", "lastPrice", "bid"):
            v = _sf(row.get(c))
            if v is not None and v > 0:
                return v
    else:
        for c in ("bid", "lastPrice", "ask"):
            v = _sf(row.get(c))
            if v is not None and v > 0:
                return v
    return None


def _pick_expiry(expirations, today: dt.date):
    choices = []
    for raw in expirations or []:
        d = _norm_date(raw)
        if not d:
            continue
        dte = (d - today).days
        if MIN_DTE <= dte <= MAX_DTE:
            choices.append((abs(dte - TARGET_DTE), dte, d))
    if not choices:
        return None
    choices.sort()
    return choices[0][2]


def _event_date(ticker_obj) -> Optional[dt.date]:
    try:
        cal = ticker_obj.calendar
        if isinstance(cal, pd.DataFrame) and not cal.empty:
            for key in ("Earnings Date", "Earnings Dates"):
                if key in cal.index:
                    vals = cal.loc[key].tolist()
                    for v in vals:
                        d = _norm_date(v)
                        if d:
                            return d
        elif isinstance(cal, dict):
            vals = cal.get("Earnings Date") or cal.get("Earnings Dates") or []
            if not isinstance(vals, (list, tuple)):
                vals = [vals]
            for v in vals:
                d = _norm_date(v)
                if d:
                    return d
    except Exception:
        return None
    return None


def _wall(df: pd.DataFrame) -> Optional[float]:
    if df is None or df.empty:
        return None
    work = df.copy()
    if "openInterest" not in work.columns:
        return None
    work["openInterest"] = pd.to_numeric(work["openInterest"], errors="coerce").fillna(0)
    work["strike"] = pd.to_numeric(work["strike"], errors="coerce")
    work = work.dropna(subset=["strike"])
    if work.empty:
        return None
    r = work.sort_values(["openInterest", "strike"], ascending=[False, True]).iloc[0]
    return _sf(r.get("strike"))


def _iv_bucket(chain: pd.DataFrame, iv: Optional[float]) -> str:
    if iv is None or chain.empty or "impliedVolatility" not in chain.columns:
        return "N/A"
    vals = pd.to_numeric(chain["impliedVolatility"], errors="coerce").dropna()
    vals = vals[vals > 0]
    if len(vals) < 8:
        return "样本不足"
    pct = float((vals <= iv).mean() * 100)
    if pct >= 80:
        return f"偏高（链内约P{pct:.0f}）"
    if pct <= 20:
        return f"偏低（链内约P{pct:.0f}）"
    return f"中性（链内约P{pct:.0f}）"


def _pick_call_structure(calls: pd.DataFrame, spot: float, dte: int):
    if calls.empty:
        return None
    work = calls.copy()
    work = work[work["strike"] > 0]
    work = work.assign(moneyness=(work["strike"] / spot - 1.0).abs())
    liquid = work[(work["volume"].fillna(0) + work["openInterest"].fillna(0) > 0)]
    if liquid.empty:
        liquid = work

    # Long call: nearest ATM with a valid executable ask/last.
    candidates = liquid.sort_values(["moneyness", "strike"])
    long_row = None
    long_price = None
    for _, row in candidates.iterrows():
        p = _best_price(row, "buy")
        if p is not None and p > 0:
            long_row, long_price = row, p
            break
    if long_row is None:
        return None

    long_strike = _sf(long_row["strike"])
    long_iv = _sf(long_row.get("impliedVolatility"))
    long_delta = _call_delta(spot, long_strike, dte, long_iv) if long_iv else None

    # Short call: prefer >= +5% OTM, lowest strike satisfying target.
    short_candidates = liquid[liquid["strike"] >= spot * 1.05].sort_values("strike")
    short_row = None
    short_price = None
    if not short_candidates.empty:
        for _, row in short_candidates.iterrows():
            p = _best_price(row, "sell")
            if p is not None and p > 0:
                short_row, short_price = row, p
                break

    if short_row is not None:
        short_strike = _sf(short_row["strike"])
        if short_strike and short_strike > long_strike and short_price is not None:
            net = long_price - short_price
            spread_width = short_strike - long_strike
            if 0 < net < spread_width:
                return {
                    "strategy": "CALL_DEBIT_SPREAD",
                    "long_strike": long_strike,
                    "short_strike": short_strike,
                    "long_price": long_price,
                    "short_price": short_price,
                    "net_debit": round(net, 2),
                    "max_loss": round(net * 100, 2),
                    "max_profit": round((short_strike - long_strike - net) * 100, 2),
                    "break_even": round(long_strike + net, 2),
                    "iv": long_iv,
                    "delta": long_delta,
                    "direction": "BULLISH",
                }

    # Fallback: Long Call only.
    return {
        "strategy": "LONG_CALL",
        "long_strike": long_strike,
        "short_strike": None,
        "long_price": long_price,
        "short_price": None,
        "net_debit": round(long_price, 2),
        "max_loss": round(long_price * 100, 2),
        "max_profit": None,
        "break_even": round(long_strike + long_price, 2),
        "iv": long_iv,
        "delta": long_delta,
        "direction": "BULLISH",
    }


def build_option_recommendation(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """为一个 Core_Dragon 构建真实期权建议；数据不足时返回 None。"""
    ticker = str(item.get("Ticker", "")).strip().upper()
    if not ticker:
        return None
    spot = _sf(item.get("Price"))
    if spot is None or spot <= 0:
        return None

    today = dt.date.today()
    try:
        obj = yf.Ticker(ticker)
        expiry = _pick_expiry(obj.options, today)
        if expiry is None:
            return None
        expiry_str = expiry.strftime("%Y-%m-%d")
        chain = obj.option_chain(expiry_str)
        calls = _clean_chain(chain.calls)
        puts = _clean_chain(chain.puts)
        if calls.empty:
            return None

        dte = (expiry - today).days
        structure = _pick_call_structure(calls, spot, dte)
        if structure is None:
            return None

        call_wall = _wall(calls)
        put_wall = _wall(puts)
        earnings = _event_date(obj)
        earnings_days = (earnings - today).days if earnings else None
        iv = structure.get("iv")
        iv_label = _iv_bucket(calls, iv)
        score = _sf(item.get("Score"))

        if structure["strategy"] == "CALL_DEBIT_SPREAD":
            rationale = "核心精选偏多；用Call Debit Spread限制最大亏损，并保留上行空间。"
        else:
            rationale = "核心精选偏多；期权链无法形成有效价差，退化为Long Call，最大风险限定为权利金。"

        if earnings_days is not None and 0 <= earnings_days <= dte:
            event_note = f"到期前约第{earnings_days}天有财报事件，需控制事件风险。"
        elif earnings_days is None:
            event_note = "财报日期未从数据源可靠取得，不把其当作已确认事件。"
        else:
            event_note = "在本次期权到期日前未识别到更近的财报事件。"

        return {
            "Ticker": ticker,
            "Name": str(item.get("Name", ticker)),
            "EntryDate": dt.datetime.now().strftime("%Y-%m-%d"),
            "UnderlyingPrice": round(spot, 2),
            "Strategy": structure["strategy"],
            "OptionType": "CALL",
            "Strike": structure["long_strike"],
            "LongStrike": structure["long_strike"],
            "ShortStrike": structure["short_strike"] or "",
            "Expiry": expiry_str,
            "DTE": dte,
            "LongPrice": structure["long_price"],
            "ShortPrice": structure["short_price"] or "",
            "NetDebit": structure["net_debit"],
            "EntryPrice": structure["net_debit"],
            "MaxLoss": structure["max_loss"],
            "MaxProfit": structure["max_profit"] or "",
            "BreakEven": structure["break_even"],
            "Delta": round(structure["delta"], 3) if structure.get("delta") is not None else "",
            "IV": round(structure["iv"], 4) if structure.get("iv") is not None else "",
            "IV_Regime": iv_label,
            "CallWall": call_wall or "",
            "PutWall": put_wall or "",
            "EarningsDate": earnings.strftime("%Y-%m-%d") if earnings else "",
            "EarningsDays": earnings_days if earnings_days is not None else "",
            "Direction": "BULLISH",
            "Status": "Active",
            "Quantity": 1,
            "StopLoss": "权利金为最大亏损；若标的趋势破坏，Review重新评估",
            "HoldPeriod": "随股票趋势动态管理，期权到期日独立",
            "Reason": rationale + " " + event_note,
            "ScanScore": score if score is not None else str(item.get("Score", "N/A")),
        }
    except Exception as e:
        print(f"⚠️ [期权] {ticker} 推荐生成失败：{e}")
        return None


def append_option_strategy(item: Dict[str, Any]) -> bool:
    rec = build_option_recommendation(item)
    if not rec:
        return False

    columns = [
        "Ticker", "Name", "EntryDate", "UnderlyingPrice", "Strategy", "OptionType", "Strike",
        "LongStrike", "ShortStrike", "Expiry", "DTE", "LongPrice", "ShortPrice",
        "NetDebit", "EntryPrice", "MaxLoss", "MaxProfit", "BreakEven", "Delta", "IV", "IV_Regime",
        "CallWall", "PutWall", "EarningsDate", "EarningsDays", "Direction", "Status",
        "Quantity", "StopLoss", "HoldPeriod", "Reason", "ScanScore",
    ]

    rows = []
    if os.path.exists(OPTION_FILE) and os.path.getsize(OPTION_FILE) > 0:
        try:
            old = pd.read_csv(OPTION_FILE, dtype=str, keep_default_na=False)
        except Exception:
            old = pd.DataFrame(columns=columns)
    else:
        old = pd.DataFrame(columns=columns)

    for c in columns:
        if c not in old.columns:
            old[c] = ""
    old = old[columns].copy()

    # 同一 ticker + expiry + 当日 recommendation 不重复增加。
    mask = (
        old["Ticker"].astype(str).str.upper().eq(rec["Ticker"].upper())
        & old["EntryDate"].astype(str).eq(rec["EntryDate"])
        & old["Expiry"].astype(str).eq(rec["Expiry"])
    )
    if mask.any():
        old.loc[mask, columns] = pd.DataFrame([rec])[columns].values[0]
        final = old
    else:
        final = pd.concat([old, pd.DataFrame([rec])[columns]], ignore_index=True)

    fd, tmp = tempfile.mkstemp(prefix=".option_strategies.", suffix=".csv", dir=".")
    os.close(fd)
    try:
        final.to_csv(tmp, index=False, encoding="utf-8", quoting=csv.QUOTE_MINIMAL)
        os.replace(tmp, OPTION_FILE)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    print(
        f"🎯 [期权推荐] {rec['Ticker']} {rec['Strategy']} "
        f"{rec['LongStrike']}" +
        (f"/{rec['ShortStrike']}" if rec['ShortStrike'] else "") +
        f" @ {rec['Expiry']} | Delta={rec['Delta'] or 'N/A'} IV={rec['IV'] or 'N/A'}"
    )
    return True


def get_recent_option_recommendations(limit: int = 20) -> list:
    if not os.path.exists(OPTION_FILE) or os.path.getsize(OPTION_FILE) == 0:
        return []
    try:
        d = pd.read_csv(OPTION_FILE, dtype=str, keep_default_na=False)
        if d.empty:
            return []
        d = d[d["Status"].astype(str).str.strip().eq("Active")].copy()
        if "EntryDate" in d.columns:
            d["_dt"] = pd.to_datetime(d["EntryDate"], errors="coerce")
            d = d.sort_values(["_dt", "Ticker"], ascending=[False, True])
        return d.drop(columns=[c for c in ["_dt"] if c in d.columns]).head(limit).to_dict("records")
    except Exception as e:
        print(f"⚠️ 读取期权推荐失败：{e}")
        return []
