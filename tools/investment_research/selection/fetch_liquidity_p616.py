"""Fetch current 60-session OHLCV for the research Top50 union and compute ADV.

Only currently listed research candidates are requested. This is not a delisted
history search and does not fill missing sessions with zero.
"""
from __future__ import annotations
import argparse, csv, json, math, tempfile
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path("data/universe/selection")
OUT = Path("data/universe/selection_inputs/liquidity_ohlcv_p616.csv")
SUMMARY = Path("data/universe/selection_inputs/liquidity_fetch_summary_p616.json")


def tickers():
    out = set()
    for name in ("value_top50.csv", "quality_top50.csv", "garp_top50.csv"):
        with (ROOT / name).open(encoding="utf-8", newline="") as f:
            out |= {r["ticker"] for r in csv.DictReader(f)}
    return sorted(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", default="6mo")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--summary", type=Path, default=SUMMARY)
    a = ap.parse_args()
    ts = tickers()
    yf.set_tz_cache_location(tempfile.mkdtemp(prefix="yf-liq-"))
    data = yf.download(ts, period=a.period, interval="1d", auto_adjust=False,
                       actions=False, threads=False, progress=False, group_by="ticker")
    today = date.today()
    rows = []
    for t in ts:
        try:
            frame = data[t] if isinstance(data.columns, pd.MultiIndex) else data
            frame = frame.dropna(subset=["Close", "Volume"]).copy()
            frame.index = pd.to_datetime(frame.index).date
            frame = frame[[d < today for d in frame.index]]
            frame = frame.sort_index()
            close = frame["Close"].astype(float)
            vol = frame["Volume"].astype(float)
            dv = close * vol
            last20 = dv.tail(20); last60 = dv.tail(60)
            adv20 = float(last20.mean()) if len(last20) >= 20 else None
            adv60 = float(last60.mean()) if len(last60) >= 60 else None
            last_date = frame.index[-1].isoformat() if len(frame) else ""
            last_close = float(close.iloc[-1]) if len(close) else None
            rows.append({"ticker": t, "last_completed_session": last_date,
                         "close": last_close, "volume": float(vol.iloc[-1]) if len(vol) else None,
                         "adv20_usd": adv20, "adv60_usd": adv60,
                         "valid_sessions_20": int(len(last20)), "valid_sessions_60": int(len(last60)),
                         "volume_source": "yfinance", "retrieved_at": datetime.now(timezone.utc).isoformat(),
                         "price_asof": last_date, "currency": "USD",
                         "adjustment": "UNADJUSTED_CLOSE_RAW_VOLUME",
                         "liquidity_status": "OK" if adv20 is not None and adv60 is not None else "PARTIAL" if adv20 is not None else "DATA_BLOCKED",
                         "liquidity_data_quality": "OK" if adv20 is not None and adv60 is not None else "PARTIAL" if adv20 is not None else "MISSING"})
        except Exception as exc:
            rows.append({"ticker": t, "last_completed_session": "", "close": None, "volume": None,
                         "adv20_usd": None, "adv60_usd": None, "valid_sessions_20": 0,
                         "valid_sessions_60": 0, "volume_source": "yfinance",
                         "retrieved_at": datetime.now(timezone.utc).isoformat(), "price_asof": "",
                         "currency": "USD", "adjustment": "UNADJUSTED_CLOSE_RAW_VOLUME",
                         "liquidity_status": "DATA_BLOCKED", "liquidity_data_quality": f"ERROR:{type(exc).__name__}:{str(exc)[:80]}"})
    a.out.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys())
    with a.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    s = {"requested": len(ts), "ok": sum(1 for r in rows if r["liquidity_status"] == "OK"),
         "partial": sum(1 for r in rows if r["liquidity_status"] == "PARTIAL"),
         "blocked": sum(1 for r in rows if r["liquidity_status"] == "DATA_BLOCKED"),
         "retrieved_at": datetime.now(timezone.utc).isoformat(), "source": "yfinance",
         "adjustment": "UNADJUSTED_CLOSE_RAW_VOLUME", "out": str(a.out)}
    a.summary.write_text(json.dumps(s, indent=2), encoding="utf-8")
    print(json.dumps(s, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
