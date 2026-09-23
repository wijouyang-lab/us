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
from typing import Any, Dict, Optional, Tuple, List

import pandas as pd
import yfinance as yf

OPTION_FILE = "option_strategies.csv"
MIN_DTE = 45
MAX_DTE = 90
TARGET_DTE = 60
RISK_FREE = 0.04
# 期权价差质量硬门槛：避免“能算出来”就直接推荐。
MIN_SPREAD_REWARD_RISK = 0.40
MAX_BREAKEVEN_PCT = 12.0
MAX_DEBIT_PCT_OF_SPOT = 4.0

# Short Put 只允许给“长期价值逻辑成立”的 Core；这是确定性风险预算，不是收益保证。
SHORT_PUT_MIN_QUANT = 70.0
SHORT_PUT_MIN_FUNDAMENTAL = 24.0
SHORT_PUT_TARGET_DELTA = 0.25
SHORT_PUT_MIN_ABS_DELTA = 0.15
SHORT_PUT_MAX_ABS_DELTA = 0.35
SHORT_PUT_MIN_STRIKE_DISCOUNT_PCT = 3.0
SHORT_PUT_MAX_STRIKE_DISCOUNT_PCT = 15.0
SHORT_PUT_MIN_PREMIUM_YIELD_PCT = 0.50
SHORT_PUT_MAX_EARNINGS_DAYS = 14
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


def _put_delta(spot: float, strike: float, dte: int, iv: float, rate: float = RISK_FREE) -> Optional[float]:
    if min(spot, strike, dte, iv) <= 0:
        return None
    t = dte / 365.0
    sigma = max(0.0001, iv)
    d1 = (math.log(spot / strike) + (rate + 0.5 * sigma * sigma) * t) / (sigma * math.sqrt(t))
    return _normal_cdf(d1) - 1.0


def _put_price(spot: float, strike: float, dte: int, iv: float, rate: float = RISK_FREE) -> Optional[float]:
    call = _call_price(spot, strike, dte, iv, rate)
    if call is None:
        return None
    t = dte / 365.0
    return call - spot + strike * math.exp(-rate * t)


def _implied_vol_put(spot: float, strike: float, dte: int, price: float, rate: float = RISK_FREE) -> Optional[float]:
    if min(spot, strike, dte, price) <= 0:
        return None
    intrinsic = max(0.0, strike * math.exp(-rate * dte / 365.0) - spot)
    if price < intrinsic * 0.98:
        return None
    lo, hi = 0.01, 5.0
    p_hi = _put_price(spot, strike, dte, hi, rate)
    if p_hi is None or price > p_hi * 1.02:
        return None
    for _ in range(60):
        mid = (lo + hi) / 2.0
        p = _put_price(spot, strike, dte, mid, rate)
        if p is None:
            return None
        if p < price:
            lo = mid
        else:
            hi = mid
    iv = (lo + hi) / 2.0
    return iv if 0.01 <= iv <= 5.0 else None


def _call_price(spot: float, strike: float, dte: int, iv: float, rate: float = RISK_FREE) -> Optional[float]:
    if min(spot, strike, dte, iv) <= 0:
        return None
    t = dte / 365.0
    sigma = max(0.0001, iv)
    root_t = math.sqrt(t)
    d1 = (math.log(spot / strike) + (rate + 0.5 * sigma * sigma) * t) / (sigma * root_t)
    d2 = d1 - sigma * root_t
    return spot * _normal_cdf(d1) - strike * math.exp(-rate * t) * _normal_cdf(d2)


def _implied_vol_call(spot: float, strike: float, dte: int, price: float, rate: float = RISK_FREE) -> Optional[float]:
    """从真实期权 mid/last 价格反解 Black-Scholes IV；失败则返回 None。"""
    if min(spot, strike, dte, price) <= 0:
        return None
    intrinsic = max(0.0, spot - strike * math.exp(-rate * dte / 365.0))
    if price < intrinsic * 0.98:
        return None
    lo, hi = 0.01, 5.0
    p_hi = _call_price(spot, strike, dte, hi, rate)
    if p_hi is None or price > p_hi * 1.02:
        return None
    for _ in range(60):
        mid = (lo + hi) / 2.0
        p = _call_price(spot, strike, dte, mid, rate)
        if p is None:
            return None
        if p < price:
            lo = mid
        else:
            hi = mid
    iv = (lo + hi) / 2.0
    return iv if 0.01 <= iv <= 5.0 else None


def _mid_or_last(row) -> Optional[float]:
    bid = _sf(row.get("bid"))
    ask = _sf(row.get("ask"))
    last = _sf(row.get("lastPrice"))
    if bid is not None and ask is not None and bid > 0 and ask >= bid:
        return (bid + ask) / 2.0
    if last is not None and last > 0:
        return last
    if ask is not None and ask > 0:
        return ask
    return bid


def _clean_chain(df: pd.DataFrame):
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


def _wall(df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """计算可解释的 Wall：优先真实 OI；没有 OI 时使用成交量代理并明确标注来源。"""
    if df is None or df.empty:
        return None
    work=df.copy()
    work["openInterest"]=pd.to_numeric(work.get("openInterest"),errors="coerce")
    work["volume"]=pd.to_numeric(work.get("volume"),errors="coerce").fillna(0)
    work["strike"]=pd.to_numeric(work.get("strike"),errors="coerce")
    work=work.dropna(subset=["strike"])
    valid=work[work["openInterest"].fillna(0)>0].copy()
    if not valid.empty:
        valid=valid.sort_values(["openInterest","volume","strike"],ascending=[False,False,True])
        row=valid.iloc[0]
        return {
            "strike":_sf(row.get("strike")),
            "open_interest":int(_sf(row.get("openInterest"),0) or 0),
            "volume":int(_sf(row.get("volume"),0) or 0),
            "source":"openInterest",
        }
    vol=work[work["volume"].fillna(0)>0].copy()
    if not vol.empty:
        vol=vol.sort_values(["volume","strike"],ascending=[False,True])
        row=vol.iloc[0]
        return {
            "strike":_sf(row.get("strike")),
            "open_interest":None,
            "volume":int(_sf(row.get("volume"),0) or 0),
            "source":"volume_proxy",
        }
    return None


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


def _long_term_value_gate(item: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Short Put 的长期价值门槛：只有愿意接货的股票才允许卖 Put。"""
    reasons=[]
    quant=_sf(item.get("Quant_Score"))
    fundamental=_sf(item.get("Fundamental_Score"))
    eps=_sf(item.get("EPS_TTM"))
    fwd_pe=_sf(item.get("PE_Forward"))
    rg=_sf(item.get("Revenue_Growth"))
    eg=_sf(item.get("Earnings_Growth"))
    ocf=_sf(item.get("Operating_Cashflow"))
    fcf=_sf(item.get("Free_Cashflow"))
    if quant is None or quant < SHORT_PUT_MIN_QUANT:
        return False,[f"Quant<{SHORT_PUT_MIN_QUANT:.0f}"]
    if fundamental is None or fundamental < SHORT_PUT_MIN_FUNDAMENTAL:
        return False,[f"基本面评分<{SHORT_PUT_MIN_FUNDAMENTAL:.0f}"]
    if eps is not None and eps <= 0:
        return False,["TTM EPS≤0，不满足长期接货逻辑"]
    if rg is not None and rg < 0:
        return False,["营收增长为负"]
    if eg is not None and eg < -0.05:
        return False,["盈利增长明显恶化"]
    if ocf is not None and fcf is not None and ocf <= 0 and fcf <= 0:
        return False,["经营现金流与自由现金流均非正"]
    if fwd_pe is not None and fwd_pe > 45:
        return False,["Forward PE>45，接货估值过高"]
    reasons.append("Quant/基本面达长期价值门槛")
    if eps is not None: reasons.append("EPS为正")
    if rg is not None and rg >= 0: reasons.append("营收非负增长")
    if eg is not None and eg >= -0.05: reasons.append("盈利未出现显著恶化")
    if (ocf is not None and ocf > 0) or (fcf is not None and fcf > 0): reasons.append("现金流为正")
    if fwd_pe is not None: reasons.append(f"Forward PE={fwd_pe:.1f}")
    return True,reasons


def _pick_short_put_structure(puts: pd.DataFrame, spot: float, dte: int, item: Dict[str, Any], earnings_days: Optional[int]):
    if puts.empty or spot <= 0:
        return None,None
    ok,reasons=_long_term_value_gate(item)
    if not ok:
        return None,reasons
    if earnings_days is not None and 0 <= earnings_days <= SHORT_PUT_MAX_EARNINGS_DAYS:
        return None,[f"财报距离仅{earnings_days}天，Short Put 暂不承担事件跳空风险"]
    work=puts[puts["strike"]>0].copy()
    work=work[work["strike"]<spot].copy()
    if work.empty:
        return None,["没有低于正股的Put执行价"]
    work["discount_pct"]=(1.0-work["strike"]/spot)*100.0
    work=work[(work["discount_pct"]>=SHORT_PUT_MIN_STRIKE_DISCOUNT_PCT)&(work["discount_pct"]<=SHORT_PUT_MAX_STRIKE_DISCOUNT_PCT)].copy()
    if work.empty:
        return None,[f"没有位于正股下方{SHORT_PUT_MIN_STRIKE_DISCOUNT_PCT:.0f}-{SHORT_PUT_MAX_STRIKE_DISCOUNT_PCT:.0f}%的Put"]
    liquid=work[(work["volume"].fillna(0)+work["openInterest"].fillna(0))>0].copy()
    if liquid.empty:
        return None,["Put链缺少有效成交量/OI"]

    candidates=[]
    for _,row in liquid.iterrows():
        strike=_sf(row.get("strike"))
        if strike is None: continue
        sell_price=_sf(row.get("bid"))
        if sell_price is None or sell_price<=0:
            sell_price=_mid_or_last(row)
        if sell_price is None or sell_price<=0: continue
        iv=_sf(row.get("impliedVolatility"))
        iv_source="Yahoo chain" if iv is not None and 0.01<=iv<=5.0 else ""
        if iv is not None and not (0.01<=iv<=5.0): iv=None
        if iv is None:
            iv=_implied_vol_put(spot,strike,dte,_mid_or_last(row) or sell_price)
            if iv is not None: iv_source="BS-derived from market mid/last"
        delta=_put_delta(spot,strike,dte,iv) if iv is not None else None
        if delta is None: continue
        abs_delta=abs(delta)
        if not (SHORT_PUT_MIN_ABS_DELTA<=abs_delta<=SHORT_PUT_MAX_ABS_DELTA): continue
        cash_secured=strike*100.0
        effective_entry=strike-sell_price
        premium_yield=sell_price/strike*100.0 if strike>0 else 0.0
        if premium_yield < SHORT_PUT_MIN_PREMIUM_YIELD_PCT: continue
        annualized=premium_yield*365.0/dte if dte>0 else None
        max_loss=max(0.0,effective_entry)*100.0
        score=(abs(abs_delta-SHORT_PUT_TARGET_DELTA)*100.0
               + abs(work.loc[_,"discount_pct"]-8.0) if _ in work.index else abs(abs_delta-SHORT_PUT_TARGET_DELTA)*100.0)
        candidates.append((score,{
            "strategy":"SHORT_PUT","long_strike":strike,"short_strike":None,"long_price":None,"short_price":sell_price,
            "net_debit":-sell_price,"premium_collected":sell_price,"cash_secured":cash_secured,
            "assignment_price":strike,"effective_entry":effective_entry,"premium_yield_pct":premium_yield,
            "annualized_yield_pct":annualized,"max_loss":max_loss,"max_profit":sell_price*100.0,
            "break_even":effective_entry,"reward_risk":None,"breakeven_pct":(effective_entry/spot-1)*100.0,
            "debit_pct":0.0,"iv":iv,"iv_source":iv_source,"delta":delta,"put_delta":delta,
            "assignment_note":"若到期价内可能被指派；持仓资金按执行价100股/张预留。","value_gate":"；".join(reasons),
        }))
    if not candidates:
        return None,["没有同时满足Delta、流动性、权利金收益与低位执行价条件的Short Put"]
    candidates.sort(key=lambda x:x[0])
    return candidates[0][1],reasons


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
    iv_source = "Yahoo chain" if long_iv is not None and 0.01 <= long_iv <= 5.0 else ""
    # Yahoo 偶尔返回空/异常 IV。此时用真实 bid/ask mid（或 last）反解 IV，
    # 这样 Delta/IV 仍然来自真实期权报价，而不是虚构参数。
    if long_iv is not None and not (0.01 <= long_iv <= 5.0):
        long_iv = None
    if long_iv is None:
        ref_price = _mid_or_last(long_row)
        long_iv = _implied_vol_call(spot, long_strike, dte, ref_price) if ref_price else None
        if long_iv is not None:
            iv_source = "BS-derived from market mid/last"
    short_row = None
    short_price = None
    short_candidates = liquid[liquid["strike"] >= spot * 1.05].sort_values("strike")
    for _, row in short_candidates.iterrows():
        p = _best_price(row, "sell")
        if p is not None and p > 0:
            short_row, short_price = row, p
            break

    if short_row is not None:
        short_strike = _sf(short_row["strike"])
        if short_strike and short_strike > long_strike:
            net = long_price - short_price
            width = short_strike - long_strike
            if 0 < net < width:
                max_loss = net * 100.0
                max_profit = (width - net) * 100.0
                break_even = long_strike + net
                reward_risk = max_profit / max_loss if max_loss > 0 else 0.0
                breakeven_pct = (break_even / spot - 1.0) * 100.0 if spot > 0 else 999.0
                debit_pct = (net / spot) * 100.0 if spot > 0 else 999.0

                # 只有同时满足收益/风险、盈亏平衡和权利金占正股比例，
                # 才把价差标为“可执行”。否则继续寻找更合理的 short strike。
                if (reward_risk >= MIN_SPREAD_REWARD_RISK
                        and breakeven_pct <= MAX_BREAKEVEN_PCT
                        and debit_pct <= MAX_DEBIT_PCT_OF_SPOT):
                    return {
                        "strategy": "CALL_DEBIT_SPREAD",
                        "long_strike": long_strike,
                        "short_strike": short_strike,
                        "long_price": long_price,
                        "short_price": short_price,
                        "net_debit": round(net, 2),
                        "max_loss": round(max_loss, 2),
                        "max_profit": round(max_profit, 2),
                        "break_even": round(break_even, 2),
                        "reward_risk": round(reward_risk, 3),
                        "breakeven_pct": round(breakeven_pct, 2),
                        "debit_pct": round(debit_pct, 2),
                        "iv": long_iv,
                        "iv_source": iv_source,
                        "delta": _call_delta(spot, long_strike, dte, long_iv) if long_iv else None,
                    }

    # Spread 无法通过质量门槛时，只有 Long Call 也满足风险预算才允许兜底。
    long_breakeven = long_strike + long_price
    long_breakeven_pct = (long_breakeven / spot - 1.0) * 100.0 if spot > 0 else 999.0
    long_debit_pct = (long_price / spot) * 100.0 if spot > 0 else 999.0
    if long_breakeven_pct > MAX_BREAKEVEN_PCT or long_debit_pct > MAX_DEBIT_PCT_OF_SPOT:
        return None
    return {
        "strategy": "LONG_CALL",
        "long_strike": long_strike,
        "short_strike": None,
        "long_price": long_price,
        "short_price": None,
        "net_debit": round(long_price, 2),
        "max_loss": round(long_price * 100, 2),
        "max_profit": None,
        "break_even": round(long_breakeven, 2),
        "reward_risk": None,
        "breakeven_pct": round(long_breakeven_pct, 2),
        "debit_pct": round(long_debit_pct, 2),
        "iv": long_iv,
        "iv_source": iv_source,
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
    technical_close = _sf(item.get("Price"))
    spot = _sf(item.get("Premarket_Price")) or technical_close
    if spot is None or spot <= 0:
        return None
    obj, expiry, calls, puts = _load_chain(ticker)
    if expiry is None or calls.empty:
        print(f"⚠️ [期权] {ticker} 没有可验证的45-90天期权链")
        return None
    dte = (expiry - _us_today()).days
    earnings = _event_date(obj) if obj is not None else None
    earnings_days = (earnings - _us_today()).days if earnings else None

    # 长期价值逻辑成立时，优先寻找 Cash-Secured Short Put；否则保留原来的 Call 结构。
    short_put, short_put_reasons = _pick_short_put_structure(puts, spot, dte, item, earnings_days)
    call_structure = _pick_call_structure(calls, spot, dte)
    if short_put:
        structure=short_put
    elif call_structure:
        structure=call_structure
    else:
        print(f"⚠️ [期权] {ticker} 没有可执行的CALL或Short Put结构")
        return None

    strategy=structure["strategy"]
    iv=structure.get("iv")
    event_note=(f"到期前约第{earnings_days}天有财报事件，需控制事件风险。" if earnings_days is not None and 0 <= earnings_days <= dte else "财报日期未可靠取得或不在本次到期窗内。")
    if strategy=="SHORT_PUT":
        rationale=(
            f"长期价值门槛通过：{structure.get('value_gate','')}；卖出现金担保Put，收取权利金，"
            f"若到期价内则按执行价接货，有效接货成本约{structure.get('effective_entry'):.2f}。"
        )
    else:
        rationale=("核心精选偏多；优先使用Call Debit Spread限制最大亏损。"
                   if strategy=="CALL_DEBIT_SPREAD"
                   else "核心精选偏多；期权链无法构建价差，使用Long Call，最大风险为权利金。")
    call_wall=_wall(calls)
    put_wall=_wall(puts)
    return {
        "Ticker": ticker,"Name":str(item.get("Name",ticker)),"EntryDate":dt.datetime.now(US_TZ).strftime("%Y-%m-%d"),
        "UnderlyingPrice":round(spot,2),"TechnicalClose":round(technical_close,2) if technical_close is not None else "",
        "PremarketPrice":round(_sf(item.get("Premarket_Price")),2) if _sf(item.get("Premarket_Price")) is not None else "",
        "PremarketChangePct":item.get("Premarket_Change_Pct",""),"PriceReference":item.get("Price_Reference","REGULAR_CLOSE"),
        "PremarketAsOfET":item.get("Premarket_AsOf_ET",""),"Strategy":strategy,"OptionType":"PUT" if strategy=="SHORT_PUT" else "CALL",
        "StrategySide":"SELL_TO_OPEN" if strategy=="SHORT_PUT" else "BUY_TO_OPEN",
        "Strike":structure["long_strike"],"LongStrike":structure["long_strike"] if strategy!="SHORT_PUT" else "",
        "ShortStrike":structure["short_strike"] or "","Expiry":expiry.strftime("%Y-%m-%d"),"DTE":dte,
        "LongPrice":structure.get("long_price") or "","ShortPrice":structure.get("short_price") or "",
        "NetDebit":structure.get("net_debit", ""),"PremiumCollected":structure.get("premium_collected", ""),"CashSecured":structure.get("cash_secured", ""),
        "AssignmentPrice":structure.get("assignment_price", ""),"EffectiveEntry":structure.get("effective_entry", ""),
        "PremiumYieldPct":round(structure.get("premium_yield_pct"),3) if structure.get("premium_yield_pct") is not None else "",
        "AnnualizedYieldPct":round(structure.get("annualized_yield_pct"),2) if structure.get("annualized_yield_pct") is not None else "",
        "EntryPrice":structure.get("premium_collected",structure.get("net_debit",0.0)),"MaxLoss":structure["max_loss"],
        "MaxProfit":structure.get("max_profit") or "","BreakEven":structure["break_even"],
        "RewardRisk":structure.get("reward_risk", ""),"BreakevenPct":structure.get("breakeven_pct",""),"DebitPctOfSpot":structure.get("debit_pct",""),
        "Delta":round(structure["delta"],3) if structure.get("delta") is not None else "","PutDelta":round(structure.get("put_delta"),3) if structure.get("put_delta") is not None else "",
        "IV":round(iv,4) if iv is not None else "","IV_Source":structure.get("iv_source","") if iv is not None else "","IV_Regime":_iv_bucket(puts if strategy=="SHORT_PUT" else calls,iv),
        "CallWall":call_wall.get("strike","") if call_wall else "","PutWall":put_wall.get("strike","") if put_wall else "",
        "CallWallOI":call_wall.get("open_interest","") if call_wall else "","PutWallOI":put_wall.get("open_interest","") if put_wall else "",
        "CallWallVolume":call_wall.get("volume","") if call_wall else "","PutWallVolume":put_wall.get("volume","") if put_wall else "",
        "CallWallSource":call_wall.get("source","") if call_wall else "NO_WALL_DATA","PutWallSource":put_wall.get("source","") if put_wall else "NO_WALL_DATA",
        "EarningsDate":earnings.strftime("%Y-%m-%d") if earnings else "","EarningsDays":earnings_days if earnings_days is not None else "",
        "Direction":"BULLISH" if strategy!="SHORT_PUT" else "BULLISH_VALUE","AssignmentRisk":"潜在指派：美国股票期权可在到期前被提前指派；程序在深度价内/临近到期时提高风险提示。" if strategy=="SHORT_PUT" else "",
        "Status":"Active","Quantity":1,
        "StopLoss":"现金担保Put无固定技术止损；若长期基本面/接货逻辑失效，应重新评估并主动平仓" if strategy=="SHORT_PUT" else "权利金为最大亏损；若正股趋势破坏，Review重新评估",
        "HoldPeriod":"持有至回补/到期；若到期价内，可能按执行价获得100股/张" if strategy=="SHORT_PUT" else "随股票趋势动态管理，期权到期日独立",
        "Reason":rationale+" "+event_note+(f" {structure.get('assignment_note','')}" if strategy=="SHORT_PUT" else ""),
        "ScanScore":item.get("Score","N/A"),
    }


def append_option_strategy(item: Dict[str, Any]) -> bool:
    rec = build_option_recommendation(item)
    if not rec:
        return False
    columns = [
        "Ticker", "Name", "EntryDate", "UnderlyingPrice", "TechnicalClose", "PremarketPrice", "PremarketChangePct", "PriceReference", "PremarketAsOfET", "Strategy", "OptionType", "Strike", "LongStrike", "ShortStrike", "Expiry", "DTE", "LongPrice", "ShortPrice",
        "NetDebit", "PremiumCollected", "CashSecured", "AssignmentPrice", "EffectiveEntry", "PremiumYieldPct", "AnnualizedYieldPct", "EntryPrice", "MaxLoss", "MaxProfit", "BreakEven", "RewardRisk", "BreakevenPct", "DebitPctOfSpot", "Delta", "PutDelta", "IV", "IV_Source", "IV_Regime", "CallWall", "PutWall", "CallWallOI", "PutWallOI", "CallWallVolume", "PutWallVolume", "CallWallSource", "PutWallSource", "EarningsDate", "EarningsDays", "Direction", "StrategySide", "AssignmentRisk", "Status", "Quantity", "StopLoss", "HoldPeriod", "Reason", "ScanScore",
    ]
    old = pd.DataFrame(columns=columns)
    if os.path.exists(OPTION_FILE) and os.path.getsize(OPTION_FILE) > 0:
        try: old = pd.read_csv(OPTION_FILE, dtype=str, keep_default_na=False)
        except Exception: pass
    for c in columns:
        if c not in old.columns: old[c] = ""
    old = old[columns].copy()
    mask = (old["Ticker"].astype(str).str.upper().eq(rec["Ticker"].upper()) & old["EntryDate"].astype(str).eq(rec["EntryDate"]) & old["Expiry"].astype(str).eq(rec["Expiry"]) & old["Strategy"].astype(str).str.upper().eq(rec["Strategy"].upper()))
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
    print(f"🎯 [期权推荐] {rec['Ticker']} {rec['Strategy']} {rec['LongStrike']}" + (f"/{rec['ShortStrike']}" if rec['ShortStrike'] else "") + f" @ {rec['Expiry']} | 权利金={rec['NetDebit']} 最大亏损={rec['MaxLoss']} 最大收益={rec['MaxProfit'] or '不限'} BE={rec['BreakEven']} R/R={rec.get('RewardRisk') or 'N/A'} Delta={rec['Delta'] or 'N/A'} IV={rec['IV'] or 'N/A'}" + (f" ({rec['IV_Source']})" if rec.get('IV_Source') else ""))
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
