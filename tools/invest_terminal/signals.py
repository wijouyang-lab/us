"""Minimal, fail-closed research signal adapters for the six style registry.

They never create orders. Missing fields return a data-blocked result rather than
a zero score or a synthetic candidate.
"""
from __future__ import annotations


def _num(s, *keys):
    for k in keys:
        v = s.get(k)
        if v is not None and isinstance(v, (int, float)):
            return float(v)
    return None


def value(s):
    pe = _num(s, "pe_ttm")
    pb = _num(s, "pb")
    if pe is None or pb is None or pe <= 0 or pb <= 0:
        return {"status": "DATA_BLOCKED", "reason": "PE_TTM/PB missing or non-positive", "score": None}
    return {"status": "RESEARCH_ONLY", "score": round((1 / pe) * 0.6 + (1 / pb) * 0.4, 6),
            "reason": "earnings yield 60% + book yield 40%; no composite validation/backtest"}


def quality(s):
    roe = _num(s, "roe")
    margin = _num(s, "profit_margin")
    if roe is None or margin is None:
        return {"status": "DATA_BLOCKED", "reason": "ROE/profit margin missing", "score": None}
    return {"status": "RESEARCH_ONLY", "score": round(roe * 0.6 + margin * 0.4, 6),
            "reason": "ROE 60% + net margin 40%; no production score"}


def garp(s):
    growth = _num(s, "revenue_growth")
    pe = _num(s, "pe_ttm")
    if growth is None:
        return {"status": "DATA_BLOCKED", "reason": "historical growth missing", "score": None}
    if pe is None or pe <= 0:
        return {"status": "DATA_BLOCKED", "reason": "forward EPS/PEG unavailable", "score": None}
    return {"status": "DATA_BLOCKED", "reason": "PEG requires verified forward EPS; historical growth alone is not GARP", "score": None}


def trend(s):
    rsi = _num(s, "rsi")
    t = s.get("technical") or {}
    ma20 = _num(t, "ma20"); ma50 = _num(t, "ma50")
    if rsi is None or ma20 is None or ma50 is None:
        return {"status": "DATA_BLOCKED", "reason": "RSI/MA20/MA50 missing", "score": None}
    return {"status": "RESEARCH_ONLY", "score": round((1 if ma20 > ma50 else -1) + (1 if 50 < rsi < 70 else 0), 3),
            "reason": "MA20>MA50 plus RSI 50-70; no PIT backtest"}


def dividend(s):
    return {"status": "DATA_BLOCKED", "reason": "No verified ticker DPS/event source; issuer cash proxy only", "score": None}


def hedge(s):
    return {"status": "DATA_BLOCKED", "reason": "No historical option chain/borrow/financing data", "score": None}


SIGNALS = {"value": value, "quality": quality, "garp": garp, "trend": trend, "dividend": dividend, "hedge": hedge}


def evaluate(stock):
    return {k: fn(stock) for k, fn in SIGNALS.items()}
