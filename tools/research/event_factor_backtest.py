"""Research-only point-in-time event-score backtest.

Signals CSV: decision_at,ticker,event_score,coverage_status
Prices CSV: date,ticker,close
Optional benchmark CSV: date,close (validation only; not exposure matched).

Entry is the first available ticker close strictly after decision_at; exit is
H price observations after entry. This is a research proxy, not a promise of
executable fills. Unknown coverage/scores are excluded, never neutral-filled.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd


def _utc(series: pd.Series, label: str) -> pd.Series:
    result = pd.to_datetime(series, errors="coerce", utc=True)
    if result.isna().any():
        raise ValueError(f"{label} contains invalid or missing timestamps")
    return result


def evaluate(signals_path: str, prices_path: str, *, horizon: int = 20,
             cost_bps_per_side: float = 5.0, quantile: float = 0.2,
             min_names_per_side: int = 5, benchmark_path: str | None = None) -> dict[str, Any]:
    if not np.isfinite(cost_bps_per_side):
        raise ValueError("cost_bps_per_side must be finite")
    if horizon < 1 or cost_bps_per_side < 0 or not 0 < quantile < 0.5 or min_names_per_side < 1:
        raise ValueError("invalid horizon, cost, quantile, or minimum names")
    s = pd.read_csv(signals_path, dtype={"ticker": str})
    required_s = {"decision_at", "ticker", "event_score", "coverage_status"}
    if not required_s.issubset(s.columns):
        raise ValueError(f"signals CSV requires {sorted(required_s)}")
    s["decision_at"] = _utc(s["decision_at"], "signals.decision_at")
    s["ticker"] = s["ticker"].astype(str).str.strip().str.upper()
    s["event_score"] = pd.to_numeric(s["event_score"], errors="coerce")
    s.loc[~np.isfinite(s["event_score"]), "event_score"] = np.nan
    s["coverage_status"] = s["coverage_status"].astype(str).str.strip().str.lower()
    if s.duplicated(["decision_at", "ticker"]).any():
        raise ValueError("duplicate decision_at/ticker signal rows")

    p = pd.read_csv(prices_path, dtype={"ticker": str})
    required_p = {"date", "ticker", "close"}
    if not required_p.issubset(p.columns):
        raise ValueError(f"prices CSV requires {sorted(required_p)}")
    p["date"] = _utc(p["date"], "prices.date")
    p["ticker"] = p["ticker"].astype(str).str.strip().str.upper()
    p["close"] = pd.to_numeric(p["close"], errors="coerce")
    p = p.dropna(subset=["close"])
    p = p[np.isfinite(p["close"]) & (p["close"] > 0)].sort_values(["ticker", "date"])
    if p.duplicated(["ticker", "date"]).any():
        raise ValueError("duplicate ticker/date price rows")
    by_ticker = {t: g.reset_index(drop=True) for t, g in p.groupby("ticker")}

    excluded_coverage = int((s["coverage_status"] != "available").sum())
    excluded_score = int(s["event_score"].isna().sum())
    eligible = s[(s["coverage_status"] == "available") & s["event_score"].notna()]
    date_rows = []
    for decision, day in eligible.groupby("decision_at", sort=True):
        candidates = []
        for row in day.itertuples(index=False):
            hist = by_ticker.get(row.ticker)
            if hist is None:
                continue
            future = hist[hist["date"] > decision]
            if len(future) <= horizon:
                continue
            entry, exit_ = float(future.iloc[0]["close"]), float(future.iloc[horizon]["close"])
            if entry > 0 and exit_ > 0:
                candidates.append((row.ticker, float(row.event_score), exit_ / entry - 1.0))
        if len(candidates) < 2 * min_names_per_side:
            continue
        cross = sorted(candidates, key=lambda x: (x[1], x[0]))
        n = max(min_names_per_side, int(np.floor(len(cross) * quantile)))
        if 2 * n > len(cross):
            continue
        shorts, longs = cross[:n], cross[-n:]
        gross = float(np.mean([x[2] for x in longs]) - np.mean([x[2] for x in shorts]))
        date_rows.append({
            "decision_at": decision.isoformat(), "eligible_names": len(cross),
            "long_names": n, "short_names": n,
            "long_short_gross_return": gross,
            "long_short_net_return": gross - 4 * cost_bps_per_side / 10000,
            "long_tickers": sorted(x[0] for x in longs),
            "short_tickers": sorted(x[0] for x in shorts),
        })
    if not date_rows:
        return {"status": "insufficient_data",
                "reason": "No decision dates had enough covered scores and complete forward prices.",
                "signals_rows": len(s), "eligible_signal_rows": len(eligible),
                "excluded_unknown_coverage": excluded_coverage,
                "excluded_missing_score": excluded_score, "decision_dates_tested": 0,
                "horizon_trading_observations": horizon, "research_only": True}
    d = pd.DataFrame(date_rows)
    r = d["long_short_net_return"].astype(float)
    equity = (1 + r).cumprod()
    dd = equity / equity.cummax() - 1
    std = float(r.std(ddof=1)) if len(r) > 1 else 0.0
    holdings = [set(x["long_tickers"]) | set(x["short_tickers"]) for x in date_rows]
    turnover = (float(np.mean([len(holdings[i] ^ holdings[i-1]) /
                 max(1, len(holdings[i] | holdings[i-1])) for i in range(1, len(holdings))]))
                if len(holdings) > 1 else None)
    benchmark = None
    if benchmark_path:
        b = pd.read_csv(benchmark_path)
        if not {"date", "close"}.issubset(b.columns):
            raise ValueError("benchmark CSV requires date,close")
        b["date"] = _utc(b["date"], "benchmark.date")
        b["close"] = pd.to_numeric(b["close"], errors="coerce")
        benchmark = {"rows": int((b["close"].notna() & np.isfinite(b["close"])).sum()),
                     "note": "Not exposure-matched; no benchmark alpha claim is made."}
    return {
        "status": "evaluated",
        "method": {"entry": "first ticker close strictly after decision_at",
                   "exit": f"close {horizon} price observations after entry",
                   "portfolio": f"equal-weight top/bottom {quantile:.0%} score tails",
                   "cost_model": "4 * one-side bps per long-short round trip",
                   "limitations": ["close-to-close proxy, not guaranteed executable fills",
                                   "overlapping holding periods are not de-overlapped",
                                   "no exposure-matched benchmark alpha estimate",
                                   "event_score must be independently validated and point-in-time"]},
        "signals_rows": len(s), "eligible_signal_rows": len(eligible),
        "excluded_unknown_coverage": excluded_coverage, "excluded_missing_score": excluded_score,
        "horizon_trading_observations": horizon, "cost_bps_per_side": cost_bps_per_side,
        "decision_dates_tested": len(d), "mean_net_return_pct": round(float(r.mean())*100, 4),
        "median_net_return_pct": round(float(r.median())*100, 4),
        "positive_date_fraction": round(float((r > 0).mean()), 4),
        "annualized_sharpe_unadjusted": round(float(r.mean()/std*np.sqrt(252/horizon)), 4) if std > 0 else None,
        "max_drawdown_pct": round(float(dd.min())*100, 4),
        "cumulative_compounded_return_pct": round(float((equity.iloc[-1]-1)*100), 4),
        "turnover_proxy": round(turnover, 4) if turnover is not None else None,
        "benchmark": benchmark, "per_decision_date": date_rows,
        "research_only": True, "production_signal_generated": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--signals", required=True)
    ap.add_argument("--prices", required=True)
    ap.add_argument("--benchmark")
    ap.add_argument("--horizon", type=int, default=20)
    ap.add_argument("--cost-bps-per-side", type=float, default=5.0)
    ap.add_argument("--quantile", type=float, default=0.2)
    ap.add_argument("--min-names-per-side", type=int, default=5)
    ap.add_argument("--output", required=True)
    a = ap.parse_args()
    result = evaluate(a.signals, a.prices, horizon=a.horizon,
                      cost_bps_per_side=a.cost_bps_per_side, quantile=a.quantile,
                      min_names_per_side=a.min_names_per_side, benchmark_path=a.benchmark)
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k != "per_decision_date"}, indent=2, sort_keys=True))
    return 0 if result["status"] == "evaluated" else 2


if __name__ == "__main__":
    raise SystemExit(main())
