"""Weekly signal generation on actual trading calendars."""
from __future__ import annotations

import pandas as pd

from .scoring import score_snapshot
from .state import TrendState, evaluate_row


def weekly_dates(dates) -> list[pd.Timestamp]:
    s = pd.Series(pd.to_datetime(sorted(set(dates))))
    return s.groupby(s.dt.to_period("W-FRI")).max().tolist()


def generate_signals(d: pd.DataFrame, start=None, end=None, min_assets: int = 2) -> pd.DataFrame:
    dates = weekly_dates(d.Date)
    calendar = sorted(pd.to_datetime(d.Date.unique()))
    prior: dict[str, TrendState] = {}
    rows = []
    for dt in dates:
        if start is not None and dt < pd.Timestamp(start):
            continue
        if end is not None and dt > pd.Timestamp(end):
            continue
        snap = d[d.Date.eq(dt)].copy()
        if snap.empty or len(snap) < min_assets:
            continue
        scored = score_snapshot(snap)
        nxt = next((x for x in calendar if x > dt), None)
        for _, r in scored.iterrows():
            st, info = evaluate_row(r, prior.get(r.Ticker, TrendState()))
            prior[r.Ticker] = st
            buy = bool(info["confirmed"] and pd.notna(r.Score))
            rows.append({
                "signal_date": dt.date().isoformat(), "next_trading_date": str(nxt.date()) if nxt else None,
                "ticker": r.Ticker, "asset_class": r.asset_class,
                "state": info["state"], "watch": info["watch"], "confirmed": info["confirmed"],
                "buy_candidate": buy, "exit_signal": info["exit_signal"], "reason": info["reason"],
                "score": None if pd.isna(r.Score) else float(r.Score), "rank": None if pd.isna(r.Score) else int(r["rank"]),
                "close": float(r.Close), "ma50": float(r.MA50), "ma200": float(r.MA200),
                "mom20": float(r.Mom20), "rel20": float(r.Rel20),
            })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["rank"] = out.groupby("signal_date")["score"].rank(method="first", ascending=False)
    return out.sort_values(["signal_date", "rank", "ticker"], na_position="last").reset_index(drop=True)
