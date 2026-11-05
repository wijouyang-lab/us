#!/usr/bin/env python3
"""P3.0 free market-data audit. Read-only; no production imports."""
from __future__ import annotations
import hashlib, json, os, tempfile, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

TICKERS = ["AAPL","MSFT","GOOGL","NVDA","CRM","ADBE","AMZN","HD","MCD","NKE",
           "CAT","HON","UNP","XOM","CVX","NEE","DUK","JNJ","PFE","UNH","MRNA",
           "JPM","BAC","BRK.B","MET","PLD","O","RIVN","QQQ","BIL","SPY"]


def _period_rows(d: pd.DataFrame) -> dict:
    idx = pd.to_datetime(d.index).tz_localize(None).normalize()
    end = idx.max()
    return {f"{n}y": int((idx >= end - pd.Timedelta(days=days)).sum()) for n, days in
            {"1":365,"2":730,"5":1825,"10":3650}.items()}


def _quality(df: pd.DataFrame, source: str, symbol: str) -> dict:
    if df is None or df.empty:
        return {"symbol": symbol, "source": source, "status": "DATA_MISSING", "rows": 0}
    d = df.copy(); d.columns = [str(c).lower() for c in d.columns]
    d.index = pd.to_datetime(d.index).tz_localize(None).normalize()
    d = d[~d.index.duplicated(keep="last")].sort_index()
    req = {"open","high","low","close","volume"}
    missing_cols = req - set(d.columns)
    bad = 0
    if not missing_cols:
        o,h,l,c,v = [pd.to_numeric(d[x], errors="coerce") for x in ("open","high","low","close","volume")]
        bad = int(((o<=0)|(h<=0)|(l<=0)|(c<=0)|(h<l)|(h<o)|(h<c)|(l>o)|(l>c)|(v<0)).sum())
    closes = pd.to_numeric(d.get("close"), errors="coerce") if "close" in d else pd.Series(dtype=float)
    jumps = (closes.pct_change().abs() > 0.35).sum() if len(closes) else 0
    return {"symbol": symbol, "source": source, "status": "OK" if not missing_cols else "DATA_INCOMPLETE",
            "rows": int(len(d)), "first": str(d.index.min().date()), "last": str(d.index.max().date()),
            "period_rows": _period_rows(d),
            "duplicates": int(df.index.duplicated().sum()), "missing_columns": sorted(missing_cols),
            "bad_ohlcv_rows": bad,
            "zero_volume_rows": int((pd.to_numeric(d.get("volume"), errors="coerce")==0).sum()) if "volume" in d else None,
            "jumps_gt_35pct": int(jumps), "adjustment_type": "raw",
            "raw_record_hash": hashlib.sha256(d.to_csv().encode()).hexdigest()}


def fetch_yf_batch() -> dict[str, pd.DataFrame]:
    import yfinance as yf
    yf.set_tz_cache_location(tempfile.mkdtemp(prefix="yf-audit-"))
    out = {}
    for s in TICKERS:
        ys = s.replace(".", "-")
        try:
            df = yf.Ticker(ys).history(period="10y", auto_adjust=False, actions=True)
            df = df.dropna(how="all")
            if len(df): out[s] = df
            print("YF", s, len(df), flush=True)
        except Exception as e:
            print("YF", s, "ERROR", type(e).__name__, flush=True)
    return out


def fetch_ak(symbol: str) -> pd.DataFrame:
    import akshare as ak
    df = ak.stock_us_daily(symbol=symbol, adjust="")
    df = df.rename(columns={"date":"Date"})
    df["Date"] = pd.to_datetime(df["Date"]); return df.set_index("Date")


def fetch_ak_all() -> dict[str, pd.DataFrame]:
    out = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(fetch_ak, s): s for s in TICKERS}
        for f in as_completed(futs):
            s = futs[f]
            try: out[s] = f.result(); print("AK", s, len(out[s]), flush=True)
            except Exception as e: print("AK", s, "ERROR", type(e).__name__, flush=True)
    return out


def finnhub_status() -> dict:
    keys = {n: os.getenv(n, "").strip() for n in ("FINNHUB_API_KEY_A", "FINNHUB_API_KEY_B", "FINNHUB_API_KEY")}
    present = {k: bool(v) for k, v in keys.items()}
    if not any(present.values()):
        return {"status": "NOT_CONFIGURED", "keys_present": present,
                "note": "No Finnhub key available; no request made. Plan/permissions NOT inferred."}
    out = {"status": "TESTED", "keys": {}}
    for name, key in keys.items():
        if not key:
            out["keys"][name] = {"present": False, "status": "NOT_CONFIGURED"}; continue
        try:
            req = urllib.request.Request("https://finnhub.io/api/v1/quote?symbol=AAPL",
                                         headers={"X-Finnhub-Token": key, "User-Agent": "research-audit"})
            with urllib.request.urlopen(req, timeout=20) as r:
                body = json.loads(r.read()); status = r.status
            out["keys"][name] = {"present": True, "http": status, "quote_has_price": bool(body.get("c")),
                                 "status": "OK" if body.get("c") else "DATA_MISSING"}
        except urllib.error.HTTPError as e:
            out["keys"][name] = {"present": True, "http": e.code,
                                 "status": "RATE_LIMITED" if e.code == 429 else "AUTH_FAILED" if e.code in (401,403) else "ERROR"}
        except Exception as e:
            out["keys"][name] = {"present": True, "status": "ERROR", "error_type": type(e).__name__}
    out["account_identity"] = "UNVERIFIED"; out["plan"] = "UNVERIFIED"; out["license_status"] = "LICENSE_UNVERIFIED"
    return out


def main():
    out = {"audited_at": datetime.now(timezone.utc).isoformat(), "tickers": TICKERS,
           "sources": {}, "coverage": []}
    print("YF batch", flush=True); yf_rows = fetch_yf_batch()
    print("YF symbols", len(yf_rows), flush=True)
    print("AK batch", flush=True); ak_rows = fetch_ak_all()
    print("AK symbols", len(ak_rows), flush=True)
    for s in TICKERS:
        if s in yf_rows: out["coverage"].append(_quality(yf_rows[s], "Yahoo/yfinance", s))
        else: out["coverage"].append({"symbol": s, "source": "Yahoo/yfinance", "status": "DATA_MISSING", "rows": 0})
        if s in ak_rows: out["coverage"].append(_quality(ak_rows[s], "AKShare/Sina", s))
        else: out["coverage"].append({"symbol": s, "source": "AKShare/Sina", "status": "DATA_MISSING", "rows": 0})
    out["sources"]["yahoo"] = {"technical": "TECHNICAL_PASS", "license": "LICENSE_UNVERIFIED",
                               "note": "public terms restrict redistribution/commercial display"}
    out["sources"]["akshare"] = {"technical": "TECHNICAL_PASS", "license": "LICENSE_UNVERIFIED",
                                 "provider": "Sina Finance staticdata", "note": "open-source library does not grant data rights"}
    out["sources"]["finnhub"] = finnhub_status()
    cross = []
    for s in TICKERS:
        if s not in yf_rows or s not in ak_rows: continue
        y = yf_rows[s].copy(); a = ak_rows[s].copy()
        y.index = pd.to_datetime(y.index).tz_localize(None).normalize(); a.index = pd.to_datetime(a.index).tz_localize(None).normalize()
        common = y.index.intersection(a.index)
        if len(common):
            diff = (y.loc[common,"Close"] - a.loc[common,"close"]).abs()
            cross.append({"symbol": s, "common_days": len(common),
                          "median_abs_diff": float(diff.median()), "max_abs_diff": float(diff.max()),
                          "days_gt_0_01": int((diff > 0.01).sum())})
    out["cross_check"] = cross
    Path("data/research/free_market_data_audit_p3.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    pd.DataFrame(out["coverage"]).to_csv("data/research/free_market_data_coverage_p3.csv", index=False)
    print("wrote", len(out["coverage"]), "coverage rows", flush=True)


if __name__ == "__main__":
    main()
