# -*- coding: utf-8 -*-
"""美股期权推荐引擎

优先使用 yfinance；失败时直接调用 Yahoo Finance options endpoint 作为第二层。
只有拿到真实期权链/报价才生成可执行策略，不伪造权利金、IV 或 Delta。
"""

import csv
import datetime as dt
import json
import math
import os
import tempfile
import time
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo
from typing import Any, Dict, Optional, Tuple

import pandas as pd
import yfinance as yf

OPTION_FILE = "option_strategies.csv"
MIN_DTE = 45
MAX_DTE = 90
TARGET_DTE = 60
RISK_FREE = 0.04
US_TZ = ZoneInfo("America/New_York")


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
        ts = pd.Timestamp(v)
        return ts.date() if not pd.isna(ts) else None
    except Exception:
        return None


def _us_today():
    return dt.datetime.now(US_TZ).date()


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
    cols = ("ask", "lastPrice", "bid") if side == "buy" else ("bid", "lastPrice", "ask")
    for c in cols:
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
    work["openInterest"] = pd.to_numeric(work.get("openInterest"), errors="coerce").fillna(0)
    work["strike"] = pd.to_numeric(work.get("strike"), errors="coerce")
    work = work.dropna(subset=["strike"])
    if work.empty:
        return None
    return _sf(work.sort_values(["openInterest", "strike"], ascending=[False, True]).iloc[0].get("strike"))


def _iv_bucket(chain: pd.DataFrame, iv: Optional[float]) -> str:
    if iv is None or chain.empty:
        return "N/A"
    vals = pd.to_numeric(chain.get("impliedVolatility"), errors="coerce").dropna()
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
    work = calls[calls["strike"] > 0].copy()
    if work.empty:
        return None
    work["moneyness"] = (work["strike"] / spot - 1.0).abs()
    liquid = work[(work["volume"].fillna(0) + work["openInterest"].fillna(0)) > 0]
    if liquid.empty:
        liquid = work

    long_row = None
    long_price = None
    for _, row in liquid.sort_values(["moneyness", "strike"]).iterrows():
        p = _best_price(row, "buy")
        if p is not None and p > 0:
            long_row, long_price = row, p
            break
    if long_row is None:
        return None

    long_strike = _sf(long_row["strike"])
    long_iv = _sf(long_row.get("impliedVolatility"))
    # Yahoo偶尔返回极小/异常IV（例如0.0000x），会把Black-Scholes Delta推到1.000，
    # 同时邮件又显示IV=N/A，形成明显的数据矛盾。异常IV不参与Delta计算。
    if long_iv is not None and not (0.01 <= long_iv <= 5.0):
        long_iv = None
    short_row = None
    short_price = None
    short_iv = None
    short_candidates = liquid[liquid["strike"] >= spot * 1.05].sort_values("strike")
    for _, row in short_candidates.iterrows():
        p = _best_price(row, "sell")
        if p is not None and p > 0:
            short_row, short_price = row, p
            short_iv = _sf(row.get("impliedVolatility"))
            if short_iv is not None and not (0.01 <= short_iv <= 5.0):
                short_iv = None
            break

    if short_row is not None:
        short_strike = _sf(short_row["strike"])
        if short_strike and short_strike > long_strike:
            net = long_price - short_price
            width = short_strike - long_strike
            if 0 < net < width:
                return {
                    "strategy": "CALL_DEBIT_SPREAD",
                    "long_strike": long_strike,
                    "short_strike": short_strike,
                    "long_price": long_price,
                    "short_price": short_price,
                    "net_debit": round(net, 2),
                    "max_loss": round(net * 100, 2),
                    "max_profit": round((width - net) * 100, 2),
                    "break_even": round(long_strike + net, 2),
                    "iv": long_iv,
                    "delta": (
                        (_call_delta(spot, long_strike, dte, long_iv) or 0.0)
                        - (_call_delta(spot, short_strike, dte, short_iv) or 0.0)
                    ) if (long_iv and short_iv) else None,
                }

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
        "delta": _call_delta(spot, long_strike, dte, long_iv) if long_iv else None,
    }


def _direct_yahoo_option_chain(ticker: str) -> Tuple[list, pd.DataFrame, pd.DataFrame]:
    """直接调用 Yahoo options endpoint，绕开 yfinance 在 Actions 环境的部分链路问题。"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150.0 Safari/537.36",
        "Accept": "application/json,text/plain,*/*",
    }
    base = f"https://query2.finance.yahoo.com/v7/finance/options/{urllib.parse.quote(ticker, safe='')}"
    req = urllib.request.Request(base, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
    result = (((payload.get("optionChain") or {}).get("result") or [None])[0])
    if not result:
        return [], pd.DataFrame(), pd.DataFrame()
    expirations = [dt.datetime.fromtimestamp(x, tz=dt.timezone.utc).date().isoformat() for x in (result.get("expirationDates") or [])]
    today = _us_today()
    expiry = _pick_expiry(expirations, today)
    if expiry is None:
        return expirations, pd.DataFrame(), pd.DataFrame()
    ts = int(dt.datetime.combine(expiry, dt.time()).replace(tzinfo=dt.timezone.utc).timestamp())
    req2 = urllib.request.Request(base + "?" + urllib.parse.urlencode({"date": ts}), headers=headers)
    with urllib.request.urlopen(req2, timeout=15) as resp:
        payload2 = json.loads(resp.read().decode("utf-8", errors="ignore"))
    result2 = (((payload2.get("optionChain") or {}).get("result") or [None])[0])
    if not result2:
        return expirations, pd.DataFrame(), pd.DataFrame()
    opt = (result2.get("options") or [{}])[0]
    calls = _clean_chain(pd.DataFrame(opt.get("calls") or []))
    puts = _clean_chain(pd.DataFrame(opt.get("puts") or []))
    return expirations, calls, puts


def _load_chain(ticker: str):
    today = _us_today()
    # Layer 1: yfinance
    try:
        obj = yf.Ticker(ticker)
        expiry = _pick_expiry(obj.options, today)
        if expiry:
            exp_str = expiry.strftime("%Y-%m-%d")
            chain = obj.option_chain(exp_str)
            calls = _clean_chain(chain.calls)
            puts = _clean_chain(chain.puts)
            if not calls.empty:
                return obj, expiry, calls, puts
    except Exception as e:
        print(f"⚠️ [期权] yfinance {ticker} 失败，尝试 Yahoo 直连：{e}")
    # Layer 2: direct Yahoo
    try:
        expirations, calls, puts = _direct_yahoo_option_chain(ticker)
        expiry = _pick_expiry(expirations, today)
        if expiry and not calls.empty:
            return None, expiry, calls, puts
    except Exception as e:
        print(f"⚠️ [期权] Yahoo直连 {ticker} 失败：{e}")
    return None, None, pd.DataFrame(), pd.DataFrame()


def build_option_recommendation(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    ticker = str(item.get("Ticker", "")).strip().upper()
    if not ticker:
        return None
    spot = _sf(item.get("Price"))
    if spot is None or spot <= 0:
        return None
    obj, expiry, calls, puts = _load_chain(ticker)
    if expiry is None or calls.empty:
        print(f"⚠️ [期权] {ticker} 没有可验证的45-90天期权链")
        return None
    dte = (expiry - _us_today()).days
    structure = _pick_call_structure(calls, spot, dte)
    if not structure:
        print(f"⚠️ [期权] {ticker} 没有可执行的CALL结构")
        return None

    earnings = _event_date(obj) if obj is not None else None
    earnings_days = (earnings - _us_today()).days if earnings else None
    iv = structure.get("iv")
    event_note = (f"到期前约第{earnings_days}天有财报事件，需控制事件风险。" if earnings_days is not None and 0 <= earnings_days <= dte else "财报日期未可靠取得或不在本次到期窗内。")
    strategy = structure["strategy"]
    # 数据一致性：IV 缺失/异常时，Delta 必须同时为空，避免出现 IV=N/A 但 Delta=1.000。
    if iv is None:
        structure["delta"] = None
    rationale = "核心精选偏多；优先使用Call Debit Spread限制最大亏损。" if strategy == "CALL_DEBIT_SPREAD" else "核心精选偏多；期权链无法构建价差，使用Long Call，最大风险为权利金。"
    return {
        "Ticker": ticker,
        "Name": str(item.get("Name", ticker)),
        "EntryDate": dt.datetime.now(US_TZ).strftime("%Y-%m-%d"),
        "UnderlyingPrice": round(spot, 2),
        "Strategy": strategy,
        "OptionType": "CALL",
        "Strike": structure["long_strike"],
        "LongStrike": structure["long_strike"],
        "ShortStrike": structure["short_strike"] or "",
        "Expiry": expiry.strftime("%Y-%m-%d"),
        "DTE": dte,
        "LongPrice": structure["long_price"],
        "ShortPrice": structure["short_price"] or "",
        "NetDebit": structure["net_debit"],
        "EntryPrice": structure["net_debit"],
        "MaxLoss": structure["max_loss"],
        "MaxProfit": structure["max_profit"] or "",
        "BreakEven": structure["break_even"],
        "Delta": round(structure["delta"], 3) if structure.get("delta") is not None else "",
        "IV": round(iv, 4) if iv is not None else "",
        "IV_Regime": _iv_bucket(calls, iv),
        "CallWall": _wall(calls) or "",
        "PutWall": _wall(puts) or "",
        "EarningsDate": earnings.strftime("%Y-%m-%d") if earnings else "",
        "EarningsDays": earnings_days if earnings_days is not None else "",
        "Direction": "BULLISH",
        "Status": "Active",
        "Quantity": 1,
        "StopLoss": "权利金为最大亏损；若正股趋势破坏，Review重新评估",
        "HoldPeriod": "随股票趋势动态管理，期权到期日独立",
        "Reason": rationale + " " + event_note,
        "ScanScore": item.get("Score", "N/A"),
    }


def append_option_strategy(item: Dict[str, Any]) -> bool:
    rec = build_option_recommendation(item)
    if not rec:
        return False
    columns = [
        "Ticker", "Name", "EntryDate", "UnderlyingPrice", "Strategy", "OptionType", "Strike", "LongStrike", "ShortStrike", "Expiry", "DTE", "LongPrice", "ShortPrice",
        "NetDebit", "EntryPrice", "MaxLoss", "MaxProfit", "BreakEven", "Delta", "IV", "IV_Regime", "CallWall", "PutWall", "EarningsDate", "EarningsDays", "Direction", "Status", "Quantity", "StopLoss", "HoldPeriod", "Reason", "ScanScore",
    ]
    old = pd.DataFrame(columns=columns)
    if os.path.exists(OPTION_FILE) and os.path.getsize(OPTION_FILE) > 0:
        try: old = pd.read_csv(OPTION_FILE, dtype=str, keep_default_na=False)
        except Exception: pass
    for c in columns:
        if c not in old.columns: old[c] = ""
    old = old[columns].copy()
    mask = old["Ticker"].astype(str).str.upper().eq(rec["Ticker"].upper()) & old["EntryDate"].astype(str).eq(rec["EntryDate"]) & old["Expiry"].astype(str).eq(rec["Expiry"])
    if mask.any():
        old.loc[mask, columns] = [rec[c] for c in columns]
        final = old
    else:
        final = pd.concat([old, pd.DataFrame([rec])[columns]], ignore_index=True)
    fd, tmp = tempfile.mkstemp(prefix=".option_strategies.", suffix=".csv", dir="."); os.close(fd)
    try:
        final.to_csv(tmp, index=False, encoding="utf-8", quoting=csv.QUOTE_MINIMAL)
        os.replace(tmp, OPTION_FILE)
    finally:
        if os.path.exists(tmp): os.remove(tmp)
    print(f"🎯 [期权推荐] {rec['Ticker']} {rec['Strategy']} {rec['LongStrike']}" + (f"/{rec['ShortStrike']}" if rec['ShortStrike'] else "") + f" @ {rec['Expiry']} | 权利金={rec['NetDebit']} Delta={rec['Delta'] or 'N/A'} IV={rec['IV'] or 'N/A'}")
    return True


def get_recent_option_recommendations(limit: int = 20) -> list:
    if not os.path.exists(OPTION_FILE) or os.path.getsize(OPTION_FILE) == 0:
        return []
    try:
        d = pd.read_csv(OPTION_FILE, dtype=str, keep_default_na=False)
        if d.empty: return []
        d = d[d["Status"].astype(str).str.strip().eq("Active")].copy()
        d["_dt"] = pd.to_datetime(d["EntryDate"], errors="coerce", format="mixed")
        d = d.sort_values(["_dt", "Ticker"], ascending=[False, True])
        return d.drop(columns=["_dt"]).head(limit).to_dict("records")
    except Exception as e:
        print(f"⚠️ 读取期权推荐失败：{e}")
        return []
