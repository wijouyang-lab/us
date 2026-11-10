"""P8 ETF multi-asset screen using free yfinance total-return-ish adjusted prices."""
from __future__ import annotations
import json, math, tempfile
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

OUT = Path("data/research/p8")
OUT.mkdir(parents=True, exist_ok=True)
TICKERS = ["SPY", "QQQ", "IWM", "TLT", "GLD", "BIL"]
START = "2007-01-01"; END = "2024-12-31"; OOS = date(2015, 1, 1)
COST_BPS = 10.0


def mdd(eq):
    peak = np.maximum.accumulate(eq); return float((eq / peak - 1).min())


def metrics(r, label):
    r = np.asarray([x for x in r if np.isfinite(x)], float); eq = np.cumprod(1 + r)
    years = len(r) / 12
    return {"name": label, "months": len(r), "cagr": float(eq[-1] ** (1 / years) - 1),
            "vol": float(r.std(ddof=1) * math.sqrt(12)), "sharpe": float(r.mean() / r.std(ddof=1) * math.sqrt(12)),
            "max_drawdown": mdd(eq), "oos": metrics_oos(r)}


def metrics_oos(r):
    return {"months": len(r)}


def main():
    yf.set_tz_cache_location(tempfile.mkdtemp(prefix="p8-etf-"))
    raw = yf.download(TICKERS, start=START, end="2025-01-01", interval="1d",
                      auto_adjust=True, actions=False, threads=False, progress=False, group_by="ticker")
    close = {}
    for t in TICKERS:
        f = raw[t] if hasattr(raw.columns, "levels") else raw
        s = f["Close"].dropna()
        close[t] = s
    px = pd.DataFrame(close).sort_index()
    px.to_csv(OUT / "etf_prices.csv")
    monthly = px.resample("ME").last()
    rets = monthly.pct_change()
    mom12 = monthly / monthly.shift(12) - 1
    vol6 = rets.rolling(6).std() * math.sqrt(12)
    ma10 = monthly.rolling(10).mean()
    rows = []; prevw = {}
    for i in range(13, len(monthly) - 1):
        d = monthly.index[i]
        # signal at month end; next month return column i+1
        assets = ["SPY", "QQQ", "IWM", "TLT", "GLD"]
        picks = [a for a in assets if mom12.loc[d, a] > 0 and monthly.loc[d, a] > ma10.loc[d, a]]
        if not picks: picks = ["BIL"]
        w = {a: 1 / len(picks) for a in picks}
        gross = sum(w[a] * rets.iloc[i + 1][a] for a in picks)
        turn = sum(abs(w.get(a, 0) - prevw.get("TREND_RISK", {}).get(a, 0)) for a in set(w) | set(prevw.get("TREND_RISK", {})))
        cost = COST_BPS / 10000 * turn
        rows.append((d.date().isoformat(), "TREND_RISK", gross - cost, picks, turn, cost))
        prevw["TREND_RISK"] = w
        # inverse-vol risk parity over all risk assets with positive 12m momentum
        rp = [a for a in assets if mom12.loc[d, a] > 0]
        if not rp: rp = ["BIL"]
        inv = {a: 1 / max(vol6.loc[d, a], 1e-9) for a in rp}
        w2 = {a: inv[a] / sum(inv.values()) for a in rp}
        gross2 = sum(w2[a] * rets.iloc[i + 1][a] for a in rp)
        turn2 = sum(abs(w2.get(a, 0) - prevw.get("RISK_PARITY", {}).get(a, 0)) for a in set(w2) | set(prevw.get("RISK_PARITY", {})))
        cost2 = COST_BPS / 10000 * turn2
        rows.append((d.date().isoformat(), "RISK_PARITY", gross2 - cost2, rp, turn2, cost2))
        prevw["RISK_PARITY"] = w2
    df = pd.DataFrame(rows, columns=["date", "strategy", "ret", "assets", "turnover_two_sided", "cost"])
    df.to_csv(OUT / "etf_strategy_returns.csv", index=False)
    out = {}
    for s in ("TREND_RISK", "RISK_PARITY"):
        x = df[df.strategy == s]
        r = x.ret.values; eq = np.cumprod(1 + r); years = len(r) / 12
        oos = x[pd.to_datetime(x.date) >= pd.Timestamp(OOS)].ret.values
        out[s] = {"months": len(r), "cagr": float(eq[-1] ** (1 / years) - 1), "vol": float(r.std(ddof=1) * math.sqrt(12)),
                  "sharpe": float(r.mean() / r.std(ddof=1) * math.sqrt(12)), "max_drawdown": mdd(eq),
                  "oos_months": len(oos), "oos_cagr": float(np.cumprod(1 + oos)[-1] ** (12 / len(oos)) - 1),
                  "oos_sharpe": float(oos.mean() / oos.std(ddof=1) * math.sqrt(12)),
                  "start": x.date.iloc[0], "end": x.date.iloc[-1]}
    bench = {}
    for t in ("SPY", "QQQ", "IWM"):
        r = rets[t].dropna().values; eq = np.cumprod(1 + r); years = len(r) / 12
        oos = rets[t][rets.index >= pd.Timestamp(OOS)].dropna().values
        bench[t] = {"months": len(r), "cagr": float(eq[-1] ** (1 / years) - 1), "sharpe": float(r.mean() / r.std(ddof=1) * math.sqrt(12)),
                    "max_drawdown": mdd(eq), "oos_cagr": float(np.cumprod(1 + oos)[-1] ** (12 / len(oos)) - 1),
                    "oos_sharpe": float(oos.mean() / oos.std(ddof=1) * math.sqrt(12))}
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "source": "yfinance auto_adjust=True",
              "tickers": TICKERS, "period": [START, END], "cost_bps_per_side": COST_BPS,
              "strategies": out, "benchmarks": bench,
              "status": "ETF_MULTIASSET_PRELIMINARY", "note": "Adjusted-close total-return proxy; no options, no leverage.",
              "cost_method": "10bps per side; cost = 10bps * L1 target-weight change; no unconditional monthly fee."}
    (OUT / "etf_multiasset_results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
