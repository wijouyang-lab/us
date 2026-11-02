"""Ledger accounting for the research Trend V1 portfolio (not production)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def metrics(daily: pd.DataFrame) -> dict:
    s = daily.set_index("date").nav.astype(float)
    r = s.pct_change().dropna()
    years = max((s.index[-1] - s.index[0]).days / 365.25, 1e-9)
    eq = s / s.iloc[0]
    dd = eq / eq.cummax() - 1
    vol = float(r.std(ddof=1) * np.sqrt(252)) if len(r) > 1 else None
    mean = float(r.mean() * 252) if len(r) else None
    downside = r[r < 0]
    dvol = float(downside.std(ddof=1) * np.sqrt(252)) if len(downside) > 1 else None
    return {
        "start": str(s.index[0].date()), "end": str(s.index[-1].date()), "days": len(s),
        "cagr": float(eq.iloc[-1] ** (1 / years) - 1),
        "total_return": float(eq.iloc[-1] - 1), "annualized_volatility": vol,
        "sharpe": float(mean / vol) if vol and vol > 0 else None,
        "sortino": float(mean / dvol) if dvol and dvol > 0 else None,
        "max_drawdown": float(dd.min()), "calmar": float((eq.iloc[-1] ** (1 / years) - 1) / abs(dd.min())) if dd.min() < 0 else None,
    }


def annual(daily: pd.DataFrame) -> list[dict]:
    d = daily.copy(); d["date"] = pd.to_datetime(d.date); d = d.set_index("date")
    out = []
    for y, g in d.groupby(d.index.year):
        out.append({"year": int(y), "return": float(g.nav.iloc[-1] / g.nav.iloc[0] - 1), "days": len(g)})
    return out
